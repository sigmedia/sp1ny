"""Parametric equalizer applied to the playback, in real time

The bands are the classic biquad filters of the Audio EQ Cookbook (R. Bristow-Johnson). numpy has no recursive filter
and a Python loop per sample is far too slow for the audio callback, so their cascade is applied as what it is: a long
impulse response, convolved block by block with FFTs (overlap-save). As the biquads are minimum phase, the response
starts at once: this adds no delay.
"""

from __future__ import annotations

import dataclasses
from typing import Literal

import numpy as np

#: The length of the FFTs of the convolution, in samples
FFT_LENGTH = 8192

#: The longest block convolved at once, in samples (longer blocks are cut)
HOP_LENGTH = 1024

#: The length kept of the impulse response: what remains of the FFT, once the block is taken out
FILTER_LENGTH = FFT_LENGTH - HOP_LENGTH

#: The number of points on which the frequency response is sampled to get the impulse response
_DESIGN_LENGTH = 32768


@dataclasses.dataclass(frozen=True)
class EqBand:
    """A band of the equalizer

    Attributes
    ----------
    kind : str
        "low_shelf", "peak" or "high_shelf"
    frequency : float
        The centre (peak) or corner (shelves) frequency, in Hz
    gain_db : float
        The gain, in dB
    q : float
        The sharpness of the band: a large Q is a narrow band
    enabled : bool
        False to leave the band out
    """

    kind: Literal["low_shelf", "peak", "high_shelf"]
    frequency: float
    gain_db: float = 0.0
    q: float = 0.71
    enabled: bool = True


DEFAULT_BANDS = (
    EqBand("low_shelf", 100.0),
    EqBand("peak", 300.0),
    EqBand("peak", 1000.0),
    EqBand("peak", 3000.0),
    EqBand("high_shelf", 8000.0),
)


def biquad_coefficients(band: EqBand, rate: float) -> tuple[np.ndarray, np.ndarray]:
    """Compute the coefficients of the filter of a band

    Parameters
    ----------
    band : EqBand
        The band
    rate : float
        The sampling rate, in Hz

    Returns
    -------
    b : np.ndarray
        The 3 coefficients of the numerator
    a : np.ndarray
        The 3 coefficients of the denominator, normalised so that a[0] = 1
    """
    amplitude = 10.0 ** (band.gain_db / 40.0)
    # NOTE: the filter makes no sense at or above the Nyquist frequency, which depends on the file and the device
    omega = 2.0 * np.pi * min(band.frequency, 0.49 * rate) / rate
    cos, alpha = np.cos(omega), np.sin(omega) / (2.0 * band.q)
    root = 2.0 * np.sqrt(amplitude) * alpha
    up, down = amplitude + 1.0, amplitude - 1.0

    if band.kind == "peak":
        b = [1.0 + alpha * amplitude, -2.0 * cos, 1.0 - alpha * amplitude]
        a = [1.0 + alpha / amplitude, -2.0 * cos, 1.0 - alpha / amplitude]
    elif band.kind == "low_shelf":
        b = [
            amplitude * (up - down * cos + root),
            2.0 * amplitude * (down - up * cos),
            amplitude * (up - down * cos - root),
        ]
        a = [up + down * cos + root, -2.0 * (down + up * cos), up + down * cos - root]
    else:
        b = [
            amplitude * (up + down * cos + root),
            -2.0 * amplitude * (down + up * cos),
            amplitude * (up + down * cos - root),
        ]
        a = [up - down * cos + root, 2.0 * (down - up * cos), up - down * cos - root]
    return np.array(b) / a[0], np.array(a) / a[0]


def frequency_response(bands: list[EqBand], rate: float, frequencies: np.ndarray) -> np.ndarray:
    """Compute the complex response of the cascade of the enabled bands

    Parameters
    ----------
    bands : list(EqBand)
        The bands
    rate : float
        The sampling rate, in Hz
    frequencies : np.ndarray
        The frequencies, in Hz

    Returns
    -------
    np.ndarray
        The response at each frequency
    """
    delay = np.exp(-2j * np.pi * np.asarray(frequencies) / rate)
    response = np.ones_like(delay)
    for band in bands:
        if band.enabled and band.gain_db != 0.0:
            b, a = biquad_coefficients(band, rate)
            response *= (b[0] + delay * (b[1] + delay * b[2])) / (1.0 + delay * (a[1] + delay * a[2]))
    return response


class Equalizer:
    """The equalizer of the player

    The GUI changes the bands at any time: it computes the new filter and publishes it with a single assignment, which
    the audio thread picks up at its next block, fading from the old filter to the new one to avoid a click.

    Attributes
    ----------
    bands : list(EqBand)
        The bands
    enabled : bool
        False to bypass the equalizer
    rate : float
        The sampling rate of the playback, in Hz
    """

    def __init__(self) -> None:
        self.bands = list(DEFAULT_BANDS)
        self.enabled = True
        self.rate = 48000.0
        self._spectrum: np.ndarray | None = None  # The filter in use, None if it would not change anything
        self._applied: np.ndarray | None = None  # The filter of the last block (audio thread only)
        self._buffer = np.zeros((FFT_LENGTH, 1), dtype=np.float32)  # The last samples played (audio thread only)

    @property
    def active(self) -> bool:
        """bool: True if the equalizer changes the signal"""
        return self._spectrum is not None

    def setBands(self, bands: list[EqBand]) -> None:
        """Change the bands

        Parameters
        ----------
        bands : list(EqBand)
            The bands
        """
        self.bands = bands
        self._design()

    def setEnabled(self, enabled: bool) -> None:
        """Bypass the equalizer or not

        Parameters
        ----------
        enabled : bool
            False to bypass it
        """
        self.enabled = enabled
        self._design()

    def responseDb(self, frequencies: np.ndarray) -> np.ndarray:
        """Compute what the equalizer does at the given frequencies

        Parameters
        ----------
        frequencies : np.ndarray
            The frequencies, in Hz

        Returns
        -------
        np.ndarray
            The gain at each frequency, in dB
        """
        if not self.enabled:
            return np.zeros_like(frequencies, dtype=float)
        return 20.0 * np.log10(np.abs(frequency_response(self.bands, self.rate, frequencies)))

    def prepare(self, rate: float, nb_channels: int) -> None:
        """Get ready for a playback (not while the audio thread is running)

        Parameters
        ----------
        rate : float
            The sampling rate of the playback, in Hz
        nb_channels : int
            The number of channels
        """
        self.rate = rate
        self._buffer = np.zeros((FFT_LENGTH, nb_channels), dtype=np.float32)
        self._design()
        self._applied = self._spectrum

    def _design(self) -> None:
        """Compute the filter of the current bands and publish it"""
        if not self.enabled or not any(band.enabled and band.gain_db != 0.0 for band in self.bands):
            self._spectrum = None
            return

        frequencies = np.arange(_DESIGN_LENGTH // 2 + 1) * self.rate / _DESIGN_LENGTH
        impulse_response = np.fft.irfft(frequency_response(self.bands, self.rate, frequencies))[:FILTER_LENGTH]
        fade = FILTER_LENGTH // 8  # What is left of the response at its end must not end abruptly
        impulse_response[-fade:] *= np.hanning(2 * fade)[fade:]
        self._spectrum = np.fft.rfft(impulse_response, FFT_LENGTH).astype(np.complex64)[:, None]

    def process(self, block: np.ndarray) -> None:
        """Filter a block in place (called by the audio callback)

        Parameters
        ----------
        block : np.ndarray
            The samples, shape (nb_frames, nb_channels), dtype float32
        """
        for start in range(0, block.shape[0], HOP_LENGTH):
            self._processHop(block[start : start + HOP_LENGTH])

    def _processHop(self, hop: np.ndarray) -> None:
        """Filter at most `HOP_LENGTH` samples in place

        Parameters
        ----------
        hop : np.ndarray
            The samples (a view on the block)
        """
        nb_frames = hop.shape[0]
        self._buffer[:-nb_frames] = self._buffer[nb_frames:]
        self._buffer[-nb_frames:] = hop

        target, applied = self._spectrum, self._applied
        if target is None and applied is None:
            return

        spectrum = np.fft.rfft(self._buffer, axis=0)

        def filtered(filter_spectrum: np.ndarray | None) -> np.ndarray:
            if filter_spectrum is None:
                return self._buffer[-nb_frames:]
            return np.fft.irfft(spectrum * filter_spectrum, FFT_LENGTH, axis=0)[-nb_frames:]

        if target is applied:
            hop[:] = filtered(target)
        else:
            ramp = np.linspace(0.0, 1.0, nb_frames, dtype=np.float32)[:, None]
            hop[:] = filtered(applied) * (1.0 - ramp) + filtered(target) * ramp
            self._applied = target
