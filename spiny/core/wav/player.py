#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHORS

    Sébastien Le Maguer <lemagues@tcd.ie>
    Mark Anderson <andersm3@tcd.ie>

DESCRIPTION

    Module containing the player class and the player object which should be used.
    This object is accessible via "spiny.core.player"

LICENSE
    MIT License, see the LICENSE file at the root of the repository
"""

from __future__ import annotations

import os
from typing import Any


import logging
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf


###############################################################################
# Functions
###############################################################################
def load_audio(filename: str | os.PathLike) -> tuple[np.ndarray, int]:
    """Load an audio file as a mono float32 signal at its native sampling rate

    The file is decoded by libsndfile (through soundfile) directly into float32, which avoids the
    float64 intermediate copies (and the heavy import) of librosa. Multi-channel files are mixed
    down to mono by averaging the channels.

    Parameters
    ----------
    filename : str or pathlib.Path
        The audio file (any format supported by libsndfile: wav, flac, ogg, ...)

    Returns
    -------
    signal : np.ndarray
        The samples, shape (nb_samples, 1), dtype float32
    sampling_rate : int
        The native sampling rate of the file
    """
    signal, sampling_rate = sf.read(filename, dtype="float32", always_2d=True)
    if signal.shape[1] > 1:
        signal = signal.mean(axis=1, dtype=np.float32, keepdims=True)
    return signal, sampling_rate


###############################################################################
# Classes
###############################################################################
class Singleton(type):
    """Metaclass ensuring that only one instance of a class is ever created"""

    _instances: dict[type, Any] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Player(metaclass=Singleton):
    """Class encapsulating an audio player.

    It relies on sounddevice (PortAudio) as qmultimedia is not available in the pyside package from conda.

    The signal is kept once, at its native sampling rate. When the output device does not accept
    that rate, the samples sent to the device are linearly interpolated block by block in the audio
    callback, so no resampled copy of the whole signal is ever stored.

    Parameters
    ----------
    chunk_size : int, optional
        Kept for backward compatibility (the block size is chosen by PortAudio). (default: 1024)
    filename : str, optional
        An audio file to load immediately. (default: None)
    """

    def __init__(self, chunk_size: int = 1024, filename: str | os.PathLike | None = None) -> None:
        self._is_playing = False
        self._is_paused = False
        self._loop_activated = False
        self._chunk_size = chunk_size
        self._position = 0  # In samples at the playback rate
        self._player_volume = 1.0
        self._last_status = None
        self._lock = threading.Lock()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._filename: str | os.PathLike | None = None
        self._sampling_rate: int | None = None
        self._play_rate = 1

        # None means "the PortAudio default output device"; devices are only queried when playing,
        # so that importing spiny works on machines without any audio output (CI, SSH, ...)
        self._device: int | None = None

        if filename is not None:
            self.loadNewWav(filename)

    def setWavData(self, wav_data: np.ndarray) -> None:
        """Replace the signal (the sampling rate is unchanged)

        Parameters
        ----------
        wav_data : np.ndarray
            The samples, shape (nb_samples,) or (nb_samples, nb_channels). The array is used as is
            (no copy).
        """
        # First be sure everything is stopped
        if self._is_playing:
            self.stop()

        self._wav = wav_data
        if len(self._wav.shape) < 2:
            self._wav = np.expand_dims(self._wav, axis=1)

    def loadNewWav(self, filename: str | os.PathLike) -> None:
        """Load an audio file at its native sampling rate (see `load_audio`)

        Parameters
        ----------
        filename : str or pathlib.Path
            The audio file
        """
        # First be sure everything is stopped
        if self._is_playing:
            self.stop()

        # Load the wav data at its native sampling rate: analysis must not depend on the audio device
        signal, sampling_rate = load_audio(filename)
        self._filename = filename
        self._sampling_rate = sampling_rate
        self.setWavData(signal)

    def setDevice(self, device: int | None) -> None:
        """Select the output device, checking that the current signal can be played on it

        Parameters
        ----------
        device : int or None
            The PortAudio device index (None for the default output device)

        Raises
        ------
        sd.PortAudioError
            if the device can play neither the native rate nor its own default rate
        """
        self._playbackRate(device)
        self._device = device

    def _playbackRate(self, device: int | None) -> int:
        """Find the rate at which the signal will be sent to the given device

        Parameters
        ----------
        device : int or None
            The PortAudio device index (None for the default output device)

        Returns
        -------
        int
            The native sampling rate if the device accepts it, otherwise the device default rate

        Raises
        ------
        sd.PortAudioError
            if the device accepts neither rate
        """
        channels = self._wav.shape[1]
        try:
            sd.check_output_settings(samplerate=self.sampling_rate, device=device, channels=channels)
            return self.sampling_rate
        except sd.PortAudioError:
            rate = int(sd.query_devices(device, "output")["default_samplerate"])
            sd.check_output_settings(samplerate=rate, device=device, channels=channels)
            return rate

    def play(self, wav_data: np.ndarray | None = None, start: float = 0, end: float = -1) -> None:
        """Play (a part of) the signal in a background thread

        Parameters
        ----------
        wav_data : np.ndarray, optional
            A new signal to load before playing (see `setWavData`). (default: None)
        start : float, optional
            The start time in seconds. (default: 0)
        end : float, optional
            The end time in seconds, -1 for the end of the signal. (default: -1)

        Raises
        ------
        sd.PortAudioError
            if the output device cannot play the signal
        """
        with self._lock:
            # If already playing, we don't need to do anything
            if self._is_playing:
                return

            # We required to play a new data, lets load it
            if wav_data is not None:
                self.setWavData(wav_data)

            # Get a rate compatible with the device (may raise sd.PortAudioError)
            self._play_rate = self._playbackRate(self._device)
            ratio = self.sampling_rate / self._play_rate  # Source samples per played sample

            # Boundaries in samples at the playback rate
            nb_played = int((self._wav.shape[0] - 1) / ratio) + 1
            start_sample = min(int(start * self._play_rate), nb_played)
            end_sample = nb_played if end == -1 else min(int(end * self._play_rate), nb_played)

            # And now play!
            self._is_playing = True
            self._position = start_sample

            # Start stream in a new (daemon) thread so that it never blocks the application exit
            new_thread = threading.Thread(
                target=self.play_handler,
                args=(self._wav, ratio, start_sample, end_sample),
                name="spiny-player",
                daemon=True,
            )
            new_thread.start()

    def pauseResume(self) -> None:
        """Toggle the pause state (the stream stays open and plays silence while paused)"""
        self._is_paused = not self._is_paused

    def stop(self) -> None:
        """Stop the playback (also when paused)"""
        self._is_playing = False
        self._is_paused = False
        self._position = 0

    def toggleLoop(self) -> None:
        """Toggle the loop mode (the played part restarts when its end is reached)"""
        self._loop_activated = not self._loop_activated

    @property
    def signal(self) -> np.ndarray:
        """np.ndarray: The loaded signal at its native sampling rate, shape (nb_samples, nb_channels)"""
        return self._wav

    @property
    def sampling_rate(self) -> int:
        """int: The native sampling rate of the loaded signal

        Raises
        ------
        RuntimeError
            if no signal has been loaded yet
        """
        if self._sampling_rate is None:
            raise RuntimeError("No signal has been loaded")
        return self._sampling_rate

    @property
    def duration(self) -> float:
        """float: The duration of the loaded signal in seconds"""
        return self._wav.shape[0] / self.sampling_rate

    @property
    def filename(self) -> str | os.PathLike | None:
        """str: The file the signal has been loaded from (None if the signal was given directly)"""
        return self._filename

    @property
    def device(self) -> int | None:
        """int: The output device index (None means the default output device)"""
        return self._device

    @property
    def is_paused(self) -> bool:
        """bool: True if the playback is paused"""
        return self._is_paused

    @property
    def loop_activated(self) -> bool:
        """bool: True if the loop mode is activated"""
        return self._loop_activated

    @property
    def volume(self) -> float:
        """float: The playback volume (between 0 and 1)"""
        return self._player_volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._player_volume = min(max(value, 0.0), 1.0)

    @property
    def position(self) -> float:
        """float: Current playback position in seconds (0 when stopped).

        This is a plain read of a value updated by the audio thread, so GUI code should poll it
        (e.g. with a QTimer) rather than being called back from the audio thread.
        """
        return self._position / self._play_rate

    @staticmethod
    def _fillBlock(out: np.ndarray, source: np.ndarray, ratio: float, position: int, frames: int) -> None:
        """Write `frames` played samples, starting at played sample `position`, into `out`

        Parameters
        ----------
        out : np.ndarray
            The output buffer, shape (>= frames, nb_channels)
        source : np.ndarray
            The signal at its native rate, shape (nb_samples, nb_channels)
        ratio : float
            The number of source samples per played sample (1.0 means no resampling)
        position : int
            The first played sample to write
        frames : int
            The number of samples to write

        Notes
        -----
        Resampling uses a linear interpolation, which is cheap enough for the real-time callback and
        fine for monitoring (it is never used for analysis).
        """
        if ratio == 1.0:
            out[:frames] = source[position : position + frames]
            return

        source_positions = (position + np.arange(frames)) * ratio
        i0 = np.minimum(source_positions.astype(np.intp), source.shape[0] - 1)
        i1 = np.minimum(i0 + 1, source.shape[0] - 1)
        frac = (source_positions - i0).astype(np.float32)[:, None]
        out[:frames] = source[i0] * (1.0 - frac) + source[i1] * frac

    def play_handler(self, source: np.ndarray, ratio: float, start: int, end: int) -> None:
        """Open the output stream and block until the playback is finished (run in the player thread)

        Parameters
        ----------
        source : np.ndarray
            The signal at its native rate, shape (nb_samples, nb_channels)
        ratio : float
            The number of source samples per played sample (1.0 means no resampling)
        start : int
            The first played sample (at the playback rate)
        end : int
            The played sample where the playback stops (at the playback rate, excluded)
        """
        event = threading.Event()
        rate = self._play_rate
        self._last_status = None

        def callback(outdata: np.ndarray, frames: int, time: Any, status: sd.CallbackFlags) -> None:
            """Fill the next output block (called by PortAudio on the real-time audio thread)

            Parameters
            ----------
            outdata : np.ndarray
                The output buffer, shape (frames, nb_channels)
            frames : int
                The number of samples requested
            time : CData
                The timing information of the stream (unused)
            status : sd.CallbackFlags
                The stream status (under/overflows)
            """
            # NOTE: this runs on the real-time audio thread: no GUI calls, no I/O
            if status:
                self._last_status = status

            chunksize = max(min(end - self._position, frames), 0)

            # Stream Stopped (checked first so that stop() also works while paused)
            if not self._is_playing:
                outdata[:] = 0
                self._position = start
                raise sd.CallbackStop()
            # If stream is paused, keep open but output zeros
            # position is not updated so can resume from same frame
            elif self._is_paused:
                outdata[:] = 0
            # Keep playing audio normally
            else:
                self._fillBlock(outdata, source, ratio, self._position, chunksize)
                if self._player_volume != 1.0:
                    outdata[:chunksize] *= self._player_volume
                if chunksize < frames:
                    outdata[chunksize:] = 0
                    if self._loop_activated:
                        self._position = start
                    else:
                        raise sd.CallbackStop()
                self._position += chunksize

        try:
            self._stream = sd.OutputStream(
                samplerate=rate,
                device=self._device,
                channels=source.shape[1],
                dtype="float32",
                callback=callback,
                finished_callback=event.set,
            )
            with self._stream:
                event.wait()  # Wait until playback is finished
        except Exception:
            self._logger.exception("Playback failed")
        finally:
            # Report the stream problems (under/overflows) recorded by the callback, outside of the audio thread
            if self._last_status:
                self._logger.warning("Playback stream status: %s", self._last_status)

            # Always leave the player in a playable state, even if the stream failed to open
            self._position = 0
            self._is_playing = False
            self._is_paused = False


player = Player()
