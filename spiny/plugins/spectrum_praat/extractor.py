"""Spectrogram extraction with Praat (through parselmouth)

The spectrogram is computed on chunks of the signal (with a margin so that the analysis windows at
the chunk boundaries see the same samples as on the full signal) and stored as 8-bit codes, so that
the memory used does not grow with the float64 copies Praat would make of a long signal.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


import numpy as np

from spiny.core import player


class SpectrumPraatExtractor:
    """Praat spectrogram of the signal loaded in the player

    Parameters
    ----------
    dynamic_range : float, optional
        The range rendered below the maximum, in dB (Praat's default display range). (default: 70)
    chunk_duration : float, optional
        The duration of the signal analysed at once, in seconds. (default: 30)

    Attributes
    ----------
    _spectrum : np.ndarray
        The spectrogram, shape (nb_frames, nb_bins), dtype uint8: the codes 0 and 255 correspond to
        (maximum - dynamic_range) dB and the maximum (in dB)
    _frameshift : float
        The time step between two frames, in seconds
    _cutoff : tuple(float, float)
        The (min, max) frequency range of the bins, in Hz
    """

    #: Margin added on each side of a chunk, in seconds (the Gaussian window spans 2 x 5 ms)
    MARGIN = 0.05

    def __init__(self, dynamic_range: float = 70.0, chunk_duration: float = 30.0) -> None:
        self._spectrum: np.ndarray = np.zeros((10, 10), dtype=np.uint8)
        self._dynamic_range = dynamic_range
        self._chunk_duration = chunk_duration
        self._frameshift = 0.002
        self._cutoff = (0.0, 5000.0)

    def _chunks(self) -> Iterator[tuple[np.ndarray, Any]]:
        """Compute the Praat spectrogram (power, Pa²/Hz) chunk by chunk

        Each chunk keeps the frames whose centre lies in its own part of the signal, so that the
        concatenation of the chunks covers the signal once.

        Yields
        ------
        power : np.ndarray
            The power of the kept frames, shape (nb_frames_in_chunk, nb_bins)
        spectrogram : parselmouth.Spectrogram
            The Praat spectrogram of the chunk (for its time step and frequency range)
        """
        import parselmouth  # NOTE: imported on first use only, to keep the startup fast and light

        signal = player.signal[:, 0]
        sampling_rate = player.sampling_rate
        chunk = max(int(self._chunk_duration * sampling_rate), 1)
        margin = int(self.MARGIN * sampling_rate)

        for start in range(0, signal.shape[0], chunk):
            end = min(start + chunk, signal.shape[0])
            first = max(start - margin, 0)
            last = min(end + margin, signal.shape[0])
            sound = parselmouth.Sound(signal[first:last].astype(np.float64), sampling_rate)
            spectrogram = sound.to_spectrogram()

            # Frame times relative to the full signal; keep the frames centred in [start, end)
            times = np.asarray(spectrogram.xs()) + first / sampling_rate
            kept = (times >= start / sampling_rate) & (times < end / sampling_rate)
            yield spectrogram.values[:, kept].T, spectrogram

    def release(self) -> None:
        """Free the extracted data (the plugin is not displayed anymore)"""
        self._spectrum = np.zeros((10, 10), dtype=np.uint8)

    def extract(self) -> np.ndarray:
        """Compute the spectrogram of the loaded signal

        Two passes are made: the first one finds the maximum power (the top of the rendered range),
        the second one quantizes the decibels on 8 bits. Only one chunk is held in floating point at
        any time.

        Returns
        -------
        np.ndarray
            The spectrogram (see the `_spectrum` attribute)

        Notes
        -----
        The frames of the different chunks are concatenated as if they were evenly spaced, starting at
        time 0: the error on the frame positions is below half a time step (1 ms by default).
        """
        # Pass 1: maximum power and output size
        maximum, nb_frames = 0.0, 0
        for power, spectrogram in self._chunks():
            if power.size > 0:
                maximum = max(maximum, float(power.max()))
            nb_frames += power.shape[0]
            nb_bins = power.shape[1]
            self._frameshift = spectrogram.get_time_step()
            self._cutoff = (spectrogram.ymin, spectrogram.ymax)

        # Pass 2: decibels relative to the maximum, mapped on [0, 255] over the dynamic range
        top_db = 10 * np.log10(max(maximum, 1e-30))
        spectrum = np.empty((nb_frames, nb_bins), dtype=np.uint8)
        position = 0
        for power, _ in self._chunks():
            db = 10 * np.log10(np.maximum(power, 1e-30)) - top_db  # <= 0
            np.clip(db, -self._dynamic_range, 0.0, out=db)
            spectrum[position : position + power.shape[0]] = np.rint(
                (db + self._dynamic_range) * (255.0 / self._dynamic_range)
            ).astype(np.uint8)
            position += power.shape[0]

        self._spectrum = spectrum
        return self._spectrum
