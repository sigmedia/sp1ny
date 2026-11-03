"""F0 track by the normalized autocorrelation of P. Boersma (1993), on whole batches of frames at once

The autocorrelation of each windowed frame is divided by the autocorrelation of the window, which removes the decay
due to the window: for a periodic signal, the result is close to 1 at the period. Its best peak gives the period.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spiny.core.overlay import frame_hop, signal_frames


@dataclass(frozen=True)
class F0Settings:
    """Parameters of the F0 analysis

    Attributes
    ----------
    time_step : float
        The time between two frames, in milliseconds
    min_f0 : float
        The lowest F0 searched, in Hz: it also sets the window, which spans three periods of it
    max_f0 : float
        The highest F0 searched, in Hz
    voicing_threshold : float
        How strong the periodicity of a frame must be for it to be voiced (between 0 and 1)
    silence_threshold : float
        Frames whose peak is below this fraction of the peak of the signal are not voiced
    """

    time_step: float = 5.0
    min_f0: float = 75.0
    max_f0: float = 500.0
    voicing_threshold: float = 0.45
    silence_threshold: float = 0.03


#: How much a low F0 is penalized, per octave (long periods are also multiples of the true one)
OCTAVE_COST = 0.01

#: The cost of a jump of one octave between two frames, and of a change between voiced and unvoiced (at a 10 ms step)
OCTAVE_JUMP_COST = 0.35
VOICING_CHANGE_COST = 0.14

#: The number of peaks of each frame considered by the path search
NB_CANDIDATES = 6

#: The frames added on each side of a batch for the path search: its ends would otherwise not know what follows
CONTEXT_FRAMES = 25

#: The band kept for the autocorrelation, as a multiple of the highest F0: this makes the inverse FFT much smaller
BAND_FACTOR = 4


def _bestPath(strengths: np.ndarray, frequencies: np.ndarray, time_step: float) -> np.ndarray:
    """Find the best path through the candidates of the frames (Viterbi), favouring a continuous F0

    Parameters
    ----------
    strengths : np.ndarray
        The strength of the candidates, shape (nb_frames, nb_candidates + 1): the last one means unvoiced
    frequencies : np.ndarray
        The frequency of the voiced candidates, in Hz, shape (nb_frames, nb_candidates)
    time_step : float
        The time between two frames, in milliseconds

    Returns
    -------
    np.ndarray
        The frequency of each frame, in Hz, NaN if it is unvoiced
    """
    nb_frames, nb_candidates = frequencies.shape
    correction = 10.0 / time_step  # NOTE: the costs are given for 10 ms: more frames mean less per frame
    log_frequencies = np.log2(frequencies)
    scores = strengths[0].copy()
    previous = np.zeros((nb_frames, nb_candidates + 1), dtype=np.intp)
    transition = np.zeros((nb_candidates + 1, nb_candidates + 1))
    transition[-1, :-1] = transition[:-1, -1] = VOICING_CHANGE_COST * correction
    jump_cost = OCTAVE_JUMP_COST * correction
    for t in range(1, nb_frames):
        jumps = np.abs(log_frequencies[t - 1, :, None] - log_frequencies[t, None, :]) * jump_cost
        transition[:-1, :-1] = np.nan_to_num(jumps, nan=1e6)
        totals = scores[:, None] - transition
        previous[t] = totals.argmax(axis=0)
        scores = totals[previous[t], np.arange(nb_candidates + 1)] + strengths[t]

    path = np.empty(nb_frames, dtype=np.intp)
    path[-1] = scores.argmax()
    for t in range(nb_frames - 1, 0, -1):
        path[t - 1] = previous[t, path[t]]
    voiced = path < nb_candidates
    result = np.full(nb_frames, np.nan)
    result[voiced] = frequencies[np.flatnonzero(voiced), path[voiced]]
    return result


def compute_f0(signal: np.ndarray, rate: int, settings: F0Settings, first_frame: int, last_frame: int) -> np.ndarray:
    """Compute the F0 of the frames [first_frame, last_frame)

    Frame t is centred on the time t × time_step, so the result does not depend on how the frames are grouped.

    Parameters
    ----------
    signal : np.ndarray
        The whole (mono) signal, shape (nb_samples,), dtype float32
    rate : int
        The sampling rate, in Hz
    settings : F0Settings
        The parameters of the analysis
    first_frame : int
        The first frame
    last_frame : int
        The frame after the last one

    Returns
    -------
    np.ndarray
        The F0 in Hz, shape (nb_frames, 1), dtype float32; NaN where the frame is not voiced
    """
    hop = frame_hop(settings.time_step, rate)
    length = round(3 * rate / settings.min_f0)
    start = max(first_frame - CONTEXT_FRAMES, 0)
    end = last_frame + CONTEXT_FRAMES
    frames = signal_frames(signal, start, end, hop, length)
    nb_frames = frames.shape[0]

    peak = max(float(signal.max(initial=0.0)), -float(signal.min(initial=0.0)))
    frame_peaks = np.abs(frames).max(axis=1)
    relative_peaks = frame_peaks / max(peak, 1e-20)

    # A quiet frame cannot be voiced (see the strength of the unvoiced candidate): no need to analyse it
    threshold = settings.voicing_threshold
    unvoiced_strengths = threshold + np.maximum(2 - relative_peaks * (1 + threshold) / settings.silence_threshold, 0)
    strengths = np.full((nb_frames, NB_CANDIDATES + 1), -np.inf)
    strengths[:, -1] = unvoiced_strengths
    frequencies = np.full((nb_frames, NB_CANDIDATES), np.nan)
    loud = np.flatnonzero((frame_peaks > 0) & (relative_peaks >= settings.silence_threshold))
    if loud.size == 0:
        return np.full((last_frame - first_frame, 1), np.nan, dtype=np.float32)

    n_fft = 1 << int(np.ceil(np.log2(2 * length)))
    nb_bins = min(int(BAND_FACTOR * settings.max_f0 * n_fft / rate), n_fft // 2) + 1
    lag_rate = 2 * (nb_bins - 1) * rate / n_fft  # The sampling rate of the band-limited autocorrelation

    def normalized_autocorrelation(x: np.ndarray) -> np.ndarray:
        spectrum = np.fft.rfft(x, n_fft, axis=-1)[..., :nb_bins]
        correlation = np.fft.irfft(np.abs(spectrum) ** 2, axis=-1)
        return correlation / np.maximum(correlation[..., :1], 1e-20)

    window = np.hanning(length).astype(np.float32)
    loud_frames = frames[loud] - frames[loud].mean(axis=1, keepdims=True)
    correlation = normalized_autocorrelation(loud_frames * window)

    first_lag = max(int(lag_rate / settings.max_f0), 1)
    last_lag = min(int(np.ceil(lag_rate / settings.min_f0)) + 1, correlation.shape[1] // 2)
    window_correlation = normalized_autocorrelation(window)[first_lag - 1 : last_lag + 1]
    values = correlation[:, first_lag - 1 : last_lag + 1] / np.maximum(window_correlation, 1e-3)

    # The peaks, refined by a parabola through the three points around each of them
    left, centre, right = values[:, :-2], values[:, 1:-1], values[:, 2:]
    is_peak = (centre > left) & (centre >= right)
    curvature = left - 2 * centre + right
    offset = 0.5 * (left - right) / np.where(is_peak & (curvature < 0), curvature, -np.inf)
    heights = centre - 0.25 * (left - right) * offset
    periods = (np.arange(first_lag, first_lag + centre.shape[1]) + offset) / lag_rate

    # The best peaks of each frame are its candidates
    peak_strengths = np.where(is_peak, heights - OCTAVE_COST * np.log2(settings.min_f0 * periods), -np.inf)
    nb_peaks = min(NB_CANDIDATES, peak_strengths.shape[1])
    best = np.argpartition(-peak_strengths, nb_peaks - 1, axis=1)[:, :nb_peaks]
    best_strengths = np.take_along_axis(peak_strengths, best, axis=1)
    strengths[loud, :nb_peaks] = best_strengths
    candidates = 1.0 / np.take_along_axis(periods, best, axis=1)
    candidates[np.isinf(best_strengths)] = np.nan
    frequencies[loud, :nb_peaks] = candidates

    track = _bestPath(strengths, frequencies, settings.time_step)
    return track[first_frame - start : last_frame - start, None].astype(np.float32)
