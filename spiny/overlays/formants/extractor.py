"""Formant tracks by linear prediction, on whole batches of frames at once so that it can follow the view in real time

For each frame: the power spectrum up to the maximum formant frequency gives the autocorrelation of the band-limited
signal, the linear prediction coefficients come from it, and the roots of the prediction polynomial are the
resonances: their angle gives the frequency and their distance to the unit circle the bandwidth.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spiny.core.overlay import frame_hop, signal_frames


@dataclass(frozen=True)
class FormantSettings:
    """Parameters of the formant analysis

    Attributes
    ----------
    time_step : float
        The time between two frames, in milliseconds
    window_length : float
        The length of the analysis window, in milliseconds
    max_frequency : float
        The frequency below which the formants are searched, in Hz (about 5000 for a man, 5500 for a woman)
    nb_formants : int
        The number of formants searched below the maximum frequency
    silence_db : float
        Frames this far below the peak of the signal have no formant, in dB
    max_bandwidth : float
        Resonances wider than this are not formants, in Hz
    """

    time_step: float = 5.0
    window_length: float = 25.0
    max_frequency: float = 5500.0
    nb_formants: int = 5
    silence_db: float = 40.0
    max_bandwidth: float = 700.0


#: The lowest frequency of a formant, in Hz
MIN_FORMANT_FREQUENCY = 90.0

#: The frequency above which the pre-emphasis raises the spectrum by 6 dB per octave, in Hz
PRE_EMPHASIS_FREQUENCY = 50.0


def compute_formants(
    signal: np.ndarray, rate: int, settings: FormantSettings, first_frame: int, last_frame: int
) -> np.ndarray:
    """Compute the formants of the frames [first_frame, last_frame)

    Frame t is centred on the time t × time_step, so the result does not depend on how the frames are grouped.

    Parameters
    ----------
    signal : np.ndarray
        The whole (mono) signal, shape (nb_samples,), dtype float32
    rate : int
        The sampling rate, in Hz
    settings : FormantSettings
        The parameters of the analysis
    first_frame : int
        The first frame
    last_frame : int
        The frame after the last one

    Returns
    -------
    np.ndarray
        The frequencies in Hz, shape (nb_frames, nb_formants), dtype float32; NaN where there is no formant
    """
    hop = frame_hop(settings.time_step, rate)
    length = max(round(settings.window_length * rate / 1000), 8)
    tracks = np.full((last_frame - first_frame, settings.nb_formants), np.nan, dtype=np.float32)

    frames = signal_frames(signal, first_frame, last_frame, hop, length)
    peak = max(float(signal.max(initial=0.0)), -float(signal.min(initial=0.0)))
    frame_peaks = np.abs(frames).max(axis=1)
    loud = np.flatnonzero((frame_peaks > 0) & (frame_peaks >= peak * 10 ** (-settings.silence_db / 20)))
    if loud.size == 0:
        return tracks

    # The power spectrum, pre-emphasized and limited to the band of the formants
    n_fft = 1 << int(np.ceil(np.log2(length)))
    nb_bins = min(int(settings.max_frequency * n_fft / rate), n_fft // 2) + 1
    top_frequency = (nb_bins - 1) * rate / n_fft
    power = np.abs(np.fft.rfft(frames[loud] * np.hamming(length).astype(np.float32), n_fft, axis=1)[:, :nb_bins]) ** 2
    omega = 2 * np.pi * np.arange(nb_bins) / n_fft
    pre_emphasis = np.exp(-2 * np.pi * PRE_EMPHASIS_FREQUENCY / rate)
    power *= (1 + pre_emphasis**2 - 2 * pre_emphasis * np.cos(omega)).astype(np.float32)

    # Linear prediction: the autocorrelation normal equations, with a little noise to keep them well conditioned
    order = 2 * settings.nb_formants
    autocorrelation = np.fft.irfft(power, axis=1)[:, : order + 1].astype(np.float64)
    autocorrelation[:, 0] *= 1 + 1e-6
    lags = np.abs(np.arange(order)[:, None] - np.arange(order)[None, :])
    coefficients = np.linalg.solve(autocorrelation[:, lags], -autocorrelation[:, 1:, None])[:, :, 0]

    # The roots of the polynomial are the eigenvalues of its companion matrix
    companion = np.zeros((loud.size, order, order))
    companion[:, 0, :] = -coefficients
    companion[:, np.arange(1, order), np.arange(order - 1)] = 1.0
    roots = np.linalg.eigvals(companion)

    # A resonance is a pair of conjugate roots: they are numbered by frequency, wide ones included, and only then the
    # wide ones are hidden, otherwise F3 would be shown as F2 when F2 is wide
    frequencies = np.angle(roots) * top_frequency / np.pi
    bandwidths = -np.log(np.maximum(np.abs(roots), 1e-12)) * 2 * top_frequency / np.pi
    is_resonance = (
        (roots.imag > 0) & (frequencies > MIN_FORMANT_FREQUENCY) & (frequencies < top_frequency - MIN_FORMANT_FREQUENCY)
    )
    order_by_frequency = np.argsort(np.where(is_resonance, frequencies, np.inf), axis=1)[:, : settings.nb_formants]
    sorted_frequencies = np.take_along_axis(frequencies, order_by_frequency, axis=1)
    sorted_is_formant = np.take_along_axis(is_resonance & (bandwidths < settings.max_bandwidth), order_by_frequency, 1)
    sorted_frequencies[~sorted_is_formant] = np.nan
    tracks[loud, : sorted_frequencies.shape[1]] = sorted_frequencies
    return tracks
