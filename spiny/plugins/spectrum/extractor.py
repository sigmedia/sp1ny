"""Spectrogram extraction with numpy only

The STFT is computed by blocks of frames (in parallel) so that the full complex STFT is never held
in memory, and the result is stored as 8-bit codes (one byte per time-frequency cell) instead of
float64 decibels. For a 10 minute signal at 16 kHz with the default parameters, this brings the
memory needed from several gigabytes down to about 150 MB (about 450 MB during the extraction).
"""

from __future__ import annotations

from collections.abc import Callable


import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from spiny.core import player

###############################################################################
# Windows
###############################################################################


def _periodic(symmetric_window: Callable[[int], np.ndarray]) -> Callable[[int], np.ndarray]:
    """Turn a symmetric window function into a periodic one (the usual choice for spectral analysis)

    Parameters
    ----------
    symmetric_window : callable
        A function taking a length N and returning a symmetric window of N samples

    Returns
    -------
    callable
        A function taking a length N and returning the periodic window of N samples
    """
    return lambda length: symmetric_window(length + 1)[:-1]


def _blackmanharris(length: int) -> np.ndarray:
    """Symmetric 4-term Blackman-Harris window

    Parameters
    ----------
    length : int
        The number of samples

    Returns
    -------
    np.ndarray
        The window
    """
    n = np.arange(length) * (2 * np.pi / max(length - 1, 1))
    return 0.35875 - 0.48829 * np.cos(n) + 0.14128 * np.cos(2 * n) - 0.01168 * np.cos(3 * n)


#: The supported analysis windows (periodic, as scipy.signal.get_window and librosa use them)
WINDOWS: dict[str, Callable[[int], np.ndarray]] = {
    "hamming": _periodic(np.hamming),
    "hann": _periodic(np.hanning),
    "blackman": _periodic(np.blackman),
    "blackmanharris": _periodic(_blackmanharris),
    "bartlett": _periodic(np.bartlett),
    "boxcar": np.ones,
}


def get_window(name: str, win_length: int, n_fft: int) -> np.ndarray:
    """Build an analysis window of `win_length` samples, zero-padded (centred) to `n_fft` samples

    Parameters
    ----------
    name : str
        The window name (one of the keys of `WINDOWS`)
    win_length : int
        The number of non-zero samples of the window
    n_fft : int
        The FFT length (>= win_length)

    Returns
    -------
    np.ndarray
        The window, shape (n_fft,), dtype float32

    Raises
    ------
    ValueError
        if the window name is unknown
    """
    if name not in WINDOWS:
        raise ValueError(f'Unknown window "{name}", supported windows are: {", ".join(WINDOWS)}')
    window = np.zeros(n_fft, dtype=np.float32)
    offset = (n_fft - win_length) // 2
    window[offset : offset + win_length] = WINDOWS[name](win_length)
    return window


###############################################################################
# STFT
###############################################################################


def stft_magnitude(
    signal: np.ndarray, first: int, last: int, n_fft: int, hop_length: int, window: np.ndarray
) -> np.ndarray:
    """Compute the STFT magnitude of the frames [first, last)

    The framing follows librosa's ``stft(center=True)``: the signal is (virtually) padded with
    n_fft // 2 zeros on each side, so frame t is centred on sample t * hop_length.

    Parameters
    ----------
    signal : np.ndarray
        The (mono) signal, shape (nb_samples,), dtype float32
    first : int
        The first frame
    last : int
        The frame after the last one
    n_fft : int
        The FFT length
    hop_length : int
        The number of samples between two consecutive frames
    window : np.ndarray
        The analysis window, shape (n_fft,)

    Returns
    -------
    np.ndarray
        The magnitudes, shape (last - first, n_fft // 2 + 1), dtype float32
    """
    pad = n_fft // 2

    # Samples covered by the frames (in the coordinates of the unpadded signal), zero outside
    start = first * hop_length - pad
    end = (last - 1) * hop_length - pad + n_fft
    segment = np.zeros(end - start, dtype=np.float32)
    src_start, src_end = max(start, 0), min(end, signal.shape[0])
    if src_end > src_start:
        segment[src_start - start : src_end - start] = signal[src_start:src_end]

    frames = np.lib.stride_tricks.sliding_window_view(segment, n_fft)[::hop_length]
    return np.abs(np.fft.rfft(frames * window, axis=1)).astype(np.float32, copy=False)


def quantize_db(
    magnitude: np.ndarray, reference: float, levels: tuple[float, float], amin: float = 1e-5, top_db: float = 80.0
) -> np.ndarray:
    """Convert magnitudes to decibels relative to `reference` and quantize them on 8 bits

    The conversion matches ``librosa.amplitude_to_db(magnitude / reference, top_db=top_db)`` (where
    `reference` is the global maximum), followed by a clipping to `levels`.

    Parameters
    ----------
    magnitude : np.ndarray
        The STFT magnitudes
    reference : float
        The magnitude corresponding to 0 dB (the maximum of the whole spectrogram)
    levels : tuple(float, float)
        The (min, max) decibel range mapped to the codes 0 and 255
    amin : float, optional
        The minimum relative amplitude (-100 dB by default) to avoid log(0). (default: 1e-5)
    top_db : float, optional
        The dynamic range kept below the maximum. (default: 80)

    Returns
    -------
    np.ndarray
        The codes, same shape as magnitude, dtype uint8
    """
    db = 20.0 * np.log10(np.maximum(magnitude / reference, amin, dtype=np.float32))
    np.maximum(db, -top_db, out=db)
    low, high = levels
    np.clip(db, low, high, out=db)
    db -= low
    db *= 255.0 / (high - low)
    return np.rint(db).astype(np.uint8)


###############################################################################
# Extractor
###############################################################################


class SpectrumExtractor:
    """Spectrogram of the signal loaded in the player

    Parameters
    ----------
    fft_length : int, optional
        Half of the FFT length (the FFT is computed on 2 * fft_length samples). (default: 2048)
    frameshift : float, optional
        The frameshift in milliseconds. (default: 5)
    framelength : float, optional
        The frame (window) length in milliseconds. (default: 5)
    window : str, optional
        The analysis window, see `WINDOWS`. (default: "hamming")
    cutoff : tuple(float, float), optional
        The (min, max) frequency range kept, in Hz. (default: (400, 5000))
    threshold_amp : tuple(float, float), optional
        The (min, max) amplitude range kept, in dB relative to the maximum. (default: (-40, 0))

    Attributes
    ----------
    _spectrum : np.ndarray
        The spectrogram, shape (nb_frames, nb_bins), dtype uint8: the codes 0 and 255 correspond to
        threshold_amp[0] and threshold_amp[1] dB
    BLOCK_SIZE : int
        The number of frames computed at once (it bounds the temporary memory of each thread)
    NB_WORKERS : int
        The number of threads computing the blocks
    """

    BLOCK_SIZE = 128
    NB_WORKERS = min(4, os.cpu_count() or 1)

    def __init__(
        self,
        fft_length: int = 2048,
        frameshift: float = 5,
        framelength: float = 5,
        window: str = "hamming",
        cutoff: tuple[float, float] = (400, 5000),
        threshold_amp: tuple[float, float] = (-40, 0),
    ) -> None:
        self._spectrum: np.ndarray = np.zeros((10, 10), dtype=np.uint8)

        # Define default parameters
        self._fft_length = fft_length
        self._frameshift = frameshift
        self._framelength = framelength
        self._window = window
        self._cutoff = cutoff
        self._threshold_amp = threshold_amp

    def release(self) -> None:
        """Free the extracted data (the plugin is not displayed anymore)"""
        self._spectrum = np.zeros((10, 10), dtype=np.uint8)

    def extract(self) -> np.ndarray:
        """Compute the spectrogram of the loaded signal

        A single pass is made over the signal, by blocks of `BLOCK_SIZE` frames computed by
        `NB_WORKERS` threads: the kept frequency bins are stored as float16 decibels while the global
        maximum (the 0 dB reference) is searched, then they are quantized on 8 bits. The peak memory
        is therefore about 3 bytes per kept time-frequency cell, 1 byte once the extraction is done.

        Returns
        -------
        np.ndarray
            The spectrogram (see the `_spectrum` attribute)

        Raises
        ------
        ValueError
            if the parameters are inconsistent
        """
        sampling_rate = player.sampling_rate
        frameshift = int(0.001 * self._frameshift * sampling_rate)
        framelength = int(0.001 * self._framelength * sampling_rate)
        if frameshift < 1:
            raise ValueError(f"The frameshift ({self._frameshift} ms) is shorter than one sample")
        if not 0 < framelength < self._fft_length:
            raise ValueError(
                f"The framelength ({framelength} samples) has to be positive and less than "
                + f"the FFT length ({self._fft_length} samples)"
            )
        if not 0 <= self._cutoff[0] < self._cutoff[1]:
            raise ValueError(f"The frequency range must satisfy 0 <= min < max (got {self._cutoff})")
        if not self._threshold_amp[0] < self._threshold_amp[1]:
            raise ValueError(f"The amplitude range must satisfy min < max (got {self._threshold_amp})")

        n_fft = self._fft_length * 2
        window = get_window(self._window, framelength, n_fft)
        signal = np.ascontiguousarray(player.signal[:, 0], dtype=np.float32)

        # Frequency bins to keep
        first_bin = int(self._cutoff[0] * n_fft / sampling_rate)
        last_bin = min(int(self._cutoff[1] * n_fft / sampling_rate), n_fft // 2 + 1)
        nb_frames = 1 + signal.shape[0] // frameshift

        # Single pass (blocks computed in parallel, numpy's FFT releases the GIL): the kept bins are stored
        # as float16 decibels while the global maximum (over all the bins, as librosa does) is searched
        absolute_db = np.empty((nb_frames, max(last_bin - first_bin, 0)), dtype=np.float16)

        def process_block(first: int) -> float:
            """Compute one block of frames and store its kept bins in decibels

            Parameters
            ----------
            first : int
                The first frame of the block

            Returns
            -------
            float
                The maximum magnitude of the block (over all the bins)
            """
            last = min(first + self.BLOCK_SIZE, nb_frames)
            magnitude = stft_magnitude(signal, first, last, n_fft, frameshift, window)
            with np.errstate(divide="ignore"):  # a null magnitude gives -inf dB, i.e. the lowest code
                absolute_db[first:last] = 20.0 * np.log10(magnitude[:, first_bin:last_bin])
            return float(magnitude.max())

        with ThreadPoolExecutor(max_workers=self.NB_WORKERS) as pool:
            reference = float(max(pool.map(process_block, range(0, nb_frames, self.BLOCK_SIZE)), default=0.0))
        reference = max(reference, float(np.finfo(np.float32).tiny))  # silent signal

        # Quantize relative to the maximum, block by block (the float16 buffer is freed when returning)
        spectrum = np.empty(absolute_db.shape, dtype=np.uint8)
        for first in range(0, nb_frames, self.BLOCK_SIZE):
            block = absolute_db[first : first + self.BLOCK_SIZE].astype(np.float32)
            spectrum[first : first + self.BLOCK_SIZE] = quantize_db(
                np.power(10.0, block / 20.0, dtype=np.float32), reference, self._threshold_amp
            )
        self._spectrum = spectrum
        return self._spectrum
