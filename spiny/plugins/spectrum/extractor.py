"""Spectrogram extraction with numpy only: the analysis of Praat (Sound: To Spectrogram...)

Only the requested time range is analysed, by blocks of frames (in parallel), and the result is stored as
8-bit codes (one byte per time-frequency cell).
"""

from __future__ import annotations

import math
import weakref
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import numpy as np

from spiny.core import player

#: The codes 0 and 255 of a spectrogram correspond to DB_FLOOR and 0 dB, so the displayed level range can change
#: without a new analysis. 0 dB is the level of a sine at the peak amplitude of the signal (see compute_spectrogram).
DB_FLOOR = -80.0


#: The levels mapped to the ends of the colormap by default, in dB
DEFAULT_DB_RANGE = (-70.0, 0.0)


def db_to_code(db: float) -> float:
    """Convert a level in dB into the 8-bit code representing it

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

    The [DB_FLOOR, 0] dB range is mapped on the codes [0, 255].

    Parameters
    ----------
    magnitude : np.ndarray
        The STFT magnitudes
    reference : float
        The magnitude corresponding to 0 dB
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


###############################################################################
# Analysis
###############################################################################


#: The window shapes of Praat
WINDOW_SHAPES = ("gaussian", "hanning", "hamming", "bartlett", "welch", "square")


@dataclass(frozen=True)
class SpectrogramSettings:
    """Parameters of the spectrogram analysis, those of Sound: To Spectrogram... (the display range is not part of them)

    Attributes
    ----------
    framelength : float
        The effective length of the analysis window, in milliseconds (5: broadband, 30: narrowband)
    max_frequency : float
        The highest frequency kept, in Hz
    frameshift : float
        The time step between two frames, in milliseconds
    frequency_step : float
        The width of the frequency bins, in Hz
    window : str
        The window shape, see `WINDOW_SHAPES`
    """

    framelength: float = 5.0
    max_frequency: float = 5000.0
    frameshift: float = 2.0
    frequency_step: float = 20.0
    window: str = "gaussian"


@dataclass(frozen=True, eq=False)
class SpectrogramSlice:
    """The spectrogram of a part of the signal

    Attributes
    ----------
    codes : np.ndarray
        The 8-bit codes, shape (nb_frames, nb_bins), dtype uint8 (see DB_FLOOR)
    start_time : float
        The time of the first frame, in seconds
    frame_duration : float
        The time between two frames, in seconds
    top_frequency : float
        The frequency at the top of the last bin, in Hz (the bins cover [0, top_frequency])
    """

    codes: np.ndarray
    start_time: float
    frame_duration: float
    top_frequency: float

    def covers(self, start_time: float, end_time: float) -> bool:
        """Tell if the slice contains a time range

        Parameters
        ----------
        start_time : float
            The start of the range, in seconds
        end_time : float
            The end of the range, in seconds

        Returns
        -------
        bool
            True if the whole range is in the slice
        """
        return self.start_time <= start_time and end_time <= self.start_time + self.codes.shape[0] * self.frame_duration


#: The number of frames computed at once (it bounds the temporary memory of each thread)
BLOCK_SIZE = 128

#: The number of threads computing the blocks
NB_WORKERS = min(4, os.cpu_count() or 1)


@dataclass(frozen=True)
class _Analysis:
    """How the frames of a signal are computed, for one method

    Attributes
    ----------
    frame_duration : float
        The time between two frames, in seconds
    origin : float
        The time where the first frame of the signal starts being displayed, in seconds
    nb_frames : int
        The number of frames of the signal
    nb_bins : int
        The number of frequency bins
    top_frequency : float
        The frequency at the top of the last bin, in Hz
    compute_block : callable
        Computes the 8-bit codes of the frames [first, last)
    """

    frame_duration: float
    origin: float
    nb_frames: int
    nb_bins: int
    top_frequency: float
    compute_block: Callable[[int, int], np.ndarray]


def _window_values(shape: str, nb_samples: int, width: float) -> np.ndarray:
    """Compute an analysis window, as Praat does

    Parameters
    ----------
    shape : str
        The window shape, see `WINDOW_SHAPES`
    nb_samples : int
        The number of samples of the window
    width : float
        The physical width of the window, in samples (a little more than `nb_samples`)

    Returns
    -------
    np.ndarray
        The window, shape (nb_samples,), dtype float64

    Raises
    ------
    ValueError
        if the window shape is unknown
    """
    if shape == "gaussian":
        edge = np.exp(-12.0)
        return (np.exp(-48.0 * ((np.arange(1, nb_samples + 1) - 0.5 * (nb_samples + 1)) / width) ** 2) - edge) / (
            1 - edge
        )
    phases = np.arange(1, nb_samples + 1) / width
    if shape == "square":
        return np.ones(nb_samples)
    if shape == "hamming":
        return 0.54 - 0.46 * np.cos(2.0 * np.pi * phases)
    if shape == "bartlett":
        return 1.0 - np.abs(2.0 * phases - 1.0)
    if shape == "welch":
        return 1.0 - (2.0 * phases - 1.0) ** 2
    if shape == "hanning":
        return 0.5 - 0.5 * np.cos(2.0 * np.pi * phases)
    raise ValueError(f'Unknown window shape "{shape}", supported shapes are: {", ".join(WINDOW_SHAPES)}')


#: The largest number of frames or frequency bins per width of the window, as Praat limits them
MAX_OVERSAMPLING = 8

#: The last maximum of an analysis: finding it needs the analysis of the whole signal, so it is only done once
_last_maximum: tuple[weakref.ref, tuple, float] | None = None


def _prepare_analysis(signal: np.ndarray, sampling_rate: int, settings: SpectrogramSettings) -> _Analysis:
    """Prepare the analysis: the same frames, window, frequency bins and power as Sound: To Spectrogram... of Praat

    Parameters
    ----------
    signal : np.ndarray
        The whole (mono) signal
    sampling_rate : int
        The sampling rate of the signal
    settings : SpectrogramSettings
        The analysis parameters

    Returns
    -------
    _Analysis
        The analysis

    Raises
    ------
    ValueError
        if the parameters are inconsistent
    """
    sample_duration = 1.0 / sampling_rate
    nyquist = 0.5 * sampling_rate
    effective_width = 0.001 * settings.framelength
    # NOTE: the Gaussian window of Praat is twice as long as its effective width
    physical_width = (2.0 if settings.window == "gaussian" else 1.0) * effective_width
    effective_time_width = effective_width / np.sqrt(np.pi)
    time_step = max(0.001 * settings.frameshift, effective_time_width / MAX_OVERSAMPLING)
    frequency_step = max(settings.frequency_step, 1.0 / effective_time_width / MAX_OVERSAMPLING)

    # NOTE: divisions by the sample duration, exactly as in Praat: multiplying by the rate does not round the same way
    half_window = int(np.floor(physical_width / sample_duration)) // 2 - 1
    nb_window = 2 * half_window
    duration = signal.shape[0] * sample_duration
    if nb_window < 1:
        raise ValueError(f"The window length ({settings.framelength} ms) is shorter than one sample")
    if physical_width > duration:
        raise ValueError(f"The signal is shorter than the analysis window ({1000 * physical_width:.0f} ms)")

    nb_frames = int(np.floor((duration - physical_width) / time_step)) + 1
    first_time = 0.5 * duration - 0.5 * nb_frames * time_step + 0.5 * time_step

    max_frequency = min(settings.max_frequency, nyquist)
    nb_bins = int(np.floor(max_frequency / frequency_step))
    n_fft = 1
    while n_fft < nb_window or n_fft < 2 * nb_bins * (nyquist / max_frequency):
        n_fft *= 2
    bin_samples = max(1, int(np.floor(frequency_step * sample_duration * n_fft)))
    frequency_step = bin_samples / (sample_duration * n_fft)
    nb_bins = int(np.floor(max_frequency / frequency_step))
    if nb_bins < 1:
        raise ValueError(f"The frequency step ({settings.frequency_step} Hz) is above the maximum frequency")

    window = _window_values(settings.window, nb_window, physical_width / sample_duration)
    scale = 1.0 / (float(np.sum(window**2)) * bin_samples)
    bin_starts = np.arange(0, nb_bins * bin_samples, bin_samples)
    offsets = np.arange(nb_window)

    def compute_power(first: int, last: int) -> np.ndarray:
        """Compute the power of the frames [first, last), as Praat stores it

        Parameters
        ----------
        first : int
            The first frame
        last : int
            The frame after the last one

        Returns
        -------
        np.ndarray
            The power, shape (last - first, nb_bins), dtype float64
        """
        times = first_time + np.arange(first, last) * time_step
        # NOTE: a time step which is not a whole number of samples gives frames which are not evenly spaced
        # shortcut: a frame exactly between two samples can start one sample away from Praat's (last bits of the time),
        #           only matters if frames must be bit-identical at such a time step
        starts = np.floor((times - 0.5 * sample_duration) / sample_duration).astype(np.intp) + 1 - half_window
        frames = signal[starts[:, None] + offsets] * window
        power = np.abs(np.fft.rfft(frames, n_fft, axis=1)[:, : nb_bins * bin_samples]) ** 2
        return np.add.reduceat(power, bin_starts, axis=1) * scale

    # The levels are relative to the maximum of the whole analysis, as what Praat shows
    global _last_maximum
    root = signal
    while isinstance(root.base, np.ndarray):
        root = root.base
    key = (sampling_rate, settings)
    if _last_maximum is not None and _last_maximum[0]() is root and _last_maximum[1] == key:
        maximum = _last_maximum[2]
    else:
        ranges = [(start, min(start + BLOCK_SIZE, nb_frames)) for start in range(0, nb_frames, BLOCK_SIZE)]
        with ThreadPoolExecutor(max_workers=NB_WORKERS) as pool:
            maximum = max(float(power.max()) for power in pool.map(lambda r: compute_power(*r), ranges))
        _last_maximum = (weakref.ref(root), key, maximum)
    reference = np.sqrt(max(maximum, float(np.finfo(np.float64).tiny)))

    def compute_block(first: int, last: int) -> np.ndarray:
        return quantize_db(np.sqrt(compute_power(first, last)), reference)

    # shortcut: the bins are drawn from 0 Hz, half an FFT bin below Praat's centres, add a y origin if a pixel matters
    return _Analysis(
        time_step, first_time - 0.5 * time_step, nb_frames, nb_bins, nb_bins * frequency_step, compute_block
    )


def compute_spectrogram(
    signal: np.ndarray,
    sampling_rate: int,
    settings: SpectrogramSettings,
    start_time: float = 0.0,
    end_time: float = math.inf,
    previous: SpectrogramSlice | None = None,
) -> SpectrogramSlice:
    """Compute the 8-bit spectrogram of a part of a signal

    The frames covering [start_time, end_time] are computed by blocks of `BLOCK_SIZE` frames, by `NB_WORKERS`
    threads. 0 dB is the maximum of the analysis of the whole signal: this reference does not depend on the analysed
    part, so the colours do not change when the view moves.

    The function only reads its arguments, so it can run in a background thread.

    Parameters
    ----------
    signal : np.ndarray
        The whole (mono) signal, shape (nb_samples,)
    sampling_rate : int
        The sampling rate of the signal
    settings : SpectrogramSettings
        The analysis parameters
    start_time : float, optional
        The start of the part to analyse, in seconds. (default: 0.0)
    end_time : float, optional
        The end of the part to analyse, in seconds. (default: the end of the signal)
    previous : SpectrogramSlice, optional
        A spectrogram of the same signal with the same settings: its frames are not computed again, which makes
        panning cheap. (default: None)

    Returns
    -------
    SpectrogramSlice
        The spectrogram of the frames covering the requested part

    Raises
    ------
    ValueError
        if the parameters are inconsistent
    """
    if settings.max_frequency <= 0:
        raise ValueError(f"The maximum frequency must be positive (got {settings.max_frequency} Hz)")
    signal = np.ascontiguousarray(signal, dtype=np.float32)
    analysis = _prepare_analysis(signal, sampling_rate, settings)

    frame_duration, origin = analysis.frame_duration, analysis.origin
    first_frame = min(max(int((start_time - origin) / frame_duration), 0), analysis.nb_frames - 1)
    end_frame = analysis.nb_frames if math.isinf(end_time) else math.ceil((end_time - origin) / frame_duration) + 1
    end_frame = max(min(end_frame, analysis.nb_frames), first_frame + 1)
    codes = np.empty((end_frame - first_frame, analysis.nb_bins), dtype=np.uint8)

    # What remains to compute: everything, or what is on each side of the frames known from `previous`
    missing = [(first_frame, end_frame)]
    if previous is not None:
        previous_first = round((previous.start_time - origin) / frame_duration)
        known_first = max(first_frame, previous_first)
        known_last = min(end_frame, previous_first + previous.codes.shape[0])
        if known_first < known_last:
            codes[known_first - first_frame : known_last - first_frame] = previous.codes[
                known_first - previous_first : known_last - previous_first
            ]
            missing = [(first_frame, known_first), (known_last, end_frame)]

    def process_block(block: tuple[int, int]) -> None:
        """Compute and quantize one block of frames (each block writes its own rows of `codes`)

        Parameters
        ----------
        block : tuple(int, int)
            The first frame of the block and the frame after its last one
        """
        codes[block[0] - first_frame : block[1] - first_frame] = analysis.compute_block(*block)

    blocks = [
        (block_start, min(block_start + BLOCK_SIZE, last))
        for first, last in missing
        for block_start in range(first, last, BLOCK_SIZE)
    ]
    with ThreadPoolExecutor(max_workers=NB_WORKERS) as pool:
        list(pool.map(process_block, blocks))  # list(): raises the errors

    return SpectrogramSlice(codes, origin + first_frame * frame_duration, frame_duration, analysis.top_frequency)


class SpectrumExtractor:
    """Spectrogram of (a part of) the signal loaded in the player

    Parameters
    ----------
    settings : SpectrogramSettings, optional
        The analysis parameters. (default: SpectrogramSettings())

    Attributes
    ----------
    settings : SpectrogramSettings
        The parameters of the current spectrogram
    spectrogram : SpectrogramSlice or None
        The current spectrogram, None if there is none
    """

    def __init__(self, settings: SpectrogramSettings = SpectrogramSettings()) -> None:
        self.settings = settings
        self.spectrogram: SpectrogramSlice | None = None

    def release(self) -> None:
        """Free the spectrogram"""
        self.spectrogram = None

    def extract(self, start_time: float = 0.0, end_time: float = math.inf) -> SpectrogramSlice:
        """Compute the spectrogram of a part of the loaded signal with the current settings

        Parameters
        ----------
        start_time : float, optional
            The start of the part to analyse, in seconds. (default: 0.0)
        end_time : float, optional
            The end of the part to analyse, in seconds. (default: the end of the signal)

        Returns
        -------
        SpectrogramSlice
            The spectrogram

        Raises
        ------
        ValueError
            if the settings are inconsistent
        """
        self.spectrogram = compute_spectrogram(
            player.signal[:, 0], player.sampling_rate, self.settings, start_time, end_time
        )
        return self.spectrogram

    def covers(self, settings: SpectrogramSettings, start_time: float, end_time: float) -> bool:
        """Tell if the current spectrogram already answers a request (so that nothing has to be computed)

        Parameters
        ----------
        settings : SpectrogramSettings
            The requested analysis parameters
        start_time : float
            The start of the requested part, in seconds
        end_time : float
            The end of the requested part, in seconds

        Returns
        -------
        bool
            True if the spectrogram has these settings and contains this part
        """
        return (
            self.spectrogram is not None and settings == self.settings and self.spectrogram.covers(start_time, end_time)
        )

    def setResult(self, settings: SpectrogramSettings, spectrogram: SpectrogramSlice) -> None:
        """Store a spectrogram computed elsewhere (e.g. in a background thread)

        Parameters
        ----------
        settings : SpectrogramSettings
            The parameters it was computed with
        spectrogram : SpectrogramSlice
            The spectrogram
        """
        self.settings = settings
        self.spectrogram = spectrogram
