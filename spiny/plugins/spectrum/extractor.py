"""Spectrogram extraction with numpy only

The STFT is computed by blocks of frames (in parallel) so that the full complex STFT is never held
in memory, and the result is stored as 8-bit codes (one byte per time-frequency cell) instead of
float64 decibels. For a 10 minute signal at 16 kHz with the default parameters, this brings the
memory needed from several gigabytes down to about 150 MB (about 450 MB during the extraction).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

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


#: The codes 0 and 255 of a spectrogram correspond to DB_FLOOR and 0 dB relative to its maximum. Below DB_FLOOR
#: everything is floored anyway (librosa's top_db), so the display range can change without a new analysis.
DB_FLOOR = -80.0


def db_to_code(db: float) -> float:
    """Convert a level in dB (relative to the maximum) into the 8-bit code representing it

    Parameters
    ----------
    db : float
        The level, between DB_FLOOR and 0

    Returns
    -------
    float
        The code, between 0 and 255
    """
    return (db - DB_FLOOR) * 255.0 / -DB_FLOOR


def quantize_db(magnitude: np.ndarray, reference: float, amin: float = 1e-5) -> np.ndarray:
    """Convert magnitudes to decibels relative to `reference` and quantize them on 8 bits

    The conversion matches ``librosa.amplitude_to_db(magnitude / reference, top_db=-DB_FLOOR)`` (where
    `reference` is the global maximum); the [DB_FLOOR, 0] dB range is mapped on the codes [0, 255].

    Parameters
    ----------
    magnitude : np.ndarray
        The STFT magnitudes
    reference : float
        The magnitude corresponding to 0 dB (the maximum of the whole spectrogram)
    amin : float, optional
        The minimum relative amplitude (-100 dB by default) to avoid log(0). (default: 1e-5)

    Returns
    -------
    np.ndarray
        The codes, same shape as magnitude, dtype uint8
    """
    db = 20.0 * np.log10(np.maximum(magnitude / reference, amin, dtype=np.float32))
    np.clip(db, DB_FLOOR, 0.0, out=db)
    db -= DB_FLOOR  # same mapping as db_to_code, done in place on the whole block
    db *= 255.0 / -DB_FLOOR
    return np.rint(db).astype(np.uint8)


def fft_length(win_length: int) -> int:
    """Choose the FFT length for a window of `win_length` samples

    The frames are zero-padded to at least 4096 samples: this does not add information, but gives a
    smooth frequency axis even for short (wideband) windows.

    Parameters
    ----------
    win_length : int
        The window length in samples

    Returns
    -------
    int
        The FFT length (a power of two)
    """
    n_fft = 4096
    while n_fft < win_length:
        n_fft *= 2
    return n_fft


###############################################################################
# Analysis
###############################################################################


@dataclass(frozen=True)
class SpectrogramSettings:
    """Parameters of the spectrogram analysis (the display range is not part of them)

    Attributes
    ----------
    frameshift : float
        The time step between two frames, in milliseconds
    framelength : float
        The length of the analysis window, in milliseconds (about 5 ms: wideband, about 30 ms: narrowband)
    window : str
        The analysis window, see `WINDOWS`
    max_frequency : float
        The highest frequency kept, in Hz (the frequency bins above are not stored)
    """

    frameshift: float = 5.0
    framelength: float = 30.0
    window: str = "hamming"
    max_frequency: float = 5000.0


#: The number of frames computed at once (it bounds the temporary memory of each thread)
BLOCK_SIZE = 128

#: The number of threads computing the blocks
NB_WORKERS = min(4, os.cpu_count() or 1)


def compute_spectrogram(
    signal: np.ndarray, sampling_rate: int, settings: SpectrogramSettings
) -> tuple[np.ndarray, float]:
    """Compute the 8-bit spectrogram of a signal

    A single pass is made over the signal, by blocks of `BLOCK_SIZE` frames computed by `NB_WORKERS`
    threads: the kept frequency bins are stored as float16 decibels while the global maximum (the 0 dB
    reference) is searched, then they are quantized on 8 bits. The peak memory is therefore about
    3 bytes per kept time-frequency cell, 1 byte once the computation is done.

    The function only reads its arguments, so it can run in a background thread.

    Parameters
    ----------
    signal : np.ndarray
        The mono signal, shape (nb_samples,)
    sampling_rate : int
        The sampling rate of the signal
    settings : SpectrogramSettings
        The analysis parameters

    Returns
    -------
    spectrum : np.ndarray
        The codes, shape (nb_frames, nb_bins), dtype uint8 (see DB_FLOOR)
    top_frequency : float
        The frequency at the top of the last kept bin, in Hz (the bins cover [0, top_frequency])

    Raises
    ------
    ValueError
        if the parameters are inconsistent
    """
    frameshift = int(0.001 * settings.frameshift * sampling_rate)
    framelength = int(0.001 * settings.framelength * sampling_rate)
    if frameshift < 1:
        raise ValueError(f"The time step ({settings.frameshift} ms) is shorter than one sample")
    if framelength < 1:
        raise ValueError(f"The window length ({settings.framelength} ms) is shorter than one sample")
    if settings.max_frequency <= 0:
        raise ValueError(f"The maximum frequency must be positive (got {settings.max_frequency} Hz)")

    n_fft = fft_length(framelength)
    window = get_window(settings.window, framelength, n_fft)
    signal = np.ascontiguousarray(signal, dtype=np.float32)
    nb_bins = min(int(settings.max_frequency * n_fft / sampling_rate) + 1, n_fft // 2 + 1)
    nb_frames = 1 + signal.shape[0] // frameshift

    # Single pass (blocks computed in parallel, numpy's FFT releases the GIL): the kept bins are stored as float16
    # decibels while the global maximum (over all the bins, as librosa does) is searched
    absolute_db = np.empty((nb_frames, nb_bins), dtype=np.float16)

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
        last = min(first + BLOCK_SIZE, nb_frames)
        magnitude = stft_magnitude(signal, first, last, n_fft, frameshift, window)
        with np.errstate(divide="ignore"):  # a null magnitude gives -inf dB, i.e. the lowest code
            absolute_db[first:last] = 20.0 * np.log10(magnitude[:, :nb_bins])
        return float(magnitude.max())

    with ThreadPoolExecutor(max_workers=NB_WORKERS) as pool:
        reference = float(max(pool.map(process_block, range(0, nb_frames, BLOCK_SIZE)), default=0.0))
    reference = max(reference, float(np.finfo(np.float32).tiny))  # silent signal

    # Quantize relative to the maximum, block by block (the float16 buffer is freed when returning)
    spectrum = np.empty(absolute_db.shape, dtype=np.uint8)
    for first in range(0, nb_frames, BLOCK_SIZE):
        block = absolute_db[first : first + BLOCK_SIZE].astype(np.float32)
        spectrum[first : first + BLOCK_SIZE] = quantize_db(np.power(10.0, block / 20.0, dtype=np.float32), reference)
    return spectrum, nb_bins * sampling_rate / n_fft


class SpectrumExtractor:
    """Spectrogram of the signal loaded in the player

    Parameters
    ----------
    settings : SpectrogramSettings, optional
        The analysis parameters. (default: SpectrogramSettings())

    Attributes
    ----------
    settings : SpectrogramSettings
        The parameters of the current spectrogram
    _spectrum : np.ndarray
        The spectrogram, shape (nb_frames, nb_bins), dtype uint8 (see DB_FLOOR)
    _top_frequency : float
        The frequency at the top of the last stored bin, in Hz
    """

    def __init__(self, settings: SpectrogramSettings = SpectrogramSettings()) -> None:
        self.settings = settings
        self.release()

    def release(self) -> None:
        """Free the spectrogram (the plugin is not displayed anymore)"""
        self._spectrum: np.ndarray = np.zeros((10, 10), dtype=np.uint8)
        self._top_frequency = self.settings.max_frequency

    def extract(self) -> np.ndarray:
        """Compute the spectrogram of the loaded signal with the current settings

        Returns
        -------
        np.ndarray
            The spectrogram (see the `_spectrum` attribute)

        Raises
        ------
        ValueError
            if the settings are inconsistent
        """
        result = compute_spectrogram(player.signal[:, 0], player.sampling_rate, self.settings)
        self.setResult(self.settings, *result)
        return self._spectrum

    def setResult(self, settings: SpectrogramSettings, spectrum: np.ndarray, top_frequency: float) -> None:
        """Store a spectrogram computed elsewhere (e.g. in a background thread)

        Parameters
        ----------
        settings : SpectrogramSettings
            The parameters it was computed with
        spectrum : np.ndarray
            The spectrogram, see compute_spectrogram
        top_frequency : float
            The frequency at the top of the last bin, see compute_spectrogram
        """
        self.settings = settings
        self._spectrum = spectrum
        self._top_frequency = top_frequency
