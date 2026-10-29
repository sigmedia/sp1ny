#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHORS

    Sébastien Le Maguer <lemagues@tcd.ie>
    Mark Anderson <andersm3@tcd.ie>

DESCRIPTION

    Module containing the player class and the player object which should be used.
    This object is accessible via "pygrad.audio.player.player"

LICENSE
    MIT License, see the LICENSE file at the root of the repository
"""

import logging
import threading

import sounddevice as sd
import librosa
import numpy as np


###############################################################################
# Classes
###############################################################################
class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Player(metaclass=Singleton):
    """Class encapsulating an audio player.

    It relies on sounddevice (PortAudio) as qmultimedia is not available in the pyside package from conda
    """

    def __init__(self, chunk_size=1024, filename=None):
        self._is_playing = False
        self._is_paused = False
        self._loop_activated = False
        self._chunk_size = chunk_size
        self._position = 0
        self._player_volume = 1.0
        self._last_status = None
        self._lock = threading.Lock()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._filename = None
        self._sampling_rate = None
        self._resampled = None
        self._play_rate = 1

        # None means "the PortAudio default output device"; devices are only queried when playing,
        # so that importing spiny works on machines without any audio output (CI, SSH, ...)
        self._device = None

        if filename is not None:
            self.loadNewWav(filename)

    def setWavData(self, wav_data):
        # First be sure everything is stopped
        if self._is_playing:
            self.stop()

        self._wav = wav_data
        if len(self._wav.shape) < 2:
            self._wav = np.expand_dims(self._wav, axis=1)
        self._resampled = None

    def loadNewWav(self, filename):
        # First be sure everything is stopped
        if self._is_playing:
            self.stop()

        # Load the wav data at its native sampling rate: analysis must not depend on the audio device
        self._filename = filename
        wav_data, self._sampling_rate = librosa.core.load(filename, sr=None)
        self.setWavData(wav_data)

    def setDevice(self, device):
        """Select the output device, checking that the current signal can be played on it

        Raises
        ------
        sd.PortAudioError
            if the device can play neither the native rate nor its own default rate
        """
        try:
            sd.check_output_settings(samplerate=self._sampling_rate, device=device, channels=self._wav.shape[1])
        except sd.PortAudioError:
            rate = sd.query_devices(device, "output")["default_samplerate"]
            sd.check_output_settings(samplerate=rate, device=device, channels=self._wav.shape[1])
        self._device = device

    def _playbackSignal(self):
        """Return the (signal, rate) to send to the device, resampling only if the device requires it"""
        try:
            sd.check_output_settings(samplerate=self._sampling_rate, device=self._device, channels=self._wav.shape[1])
            return self._wav, self._sampling_rate
        except sd.PortAudioError:
            rate = int(sd.query_devices(self._device, "output")["default_samplerate"])
            sd.check_output_settings(samplerate=rate, device=self._device, channels=self._wav.shape[1])
            if (self._resampled is None) or (self._resampled[1] != rate):
                signal = librosa.resample(self._wav[:, 0], orig_sr=self._sampling_rate, target_sr=rate)
                self._resampled = (np.expand_dims(signal, axis=1), rate)
            return self._resampled

    def play(self, wav_data=None, start=0, end=-1):
        """Play the signal given in parameters

        Parameters
        ----------
        sig_array : np.array
           The signal samples

        sampling_rate : int
           The sample rate

        viewBox: pg.pyqtgraph.ViewBox
           The view box currently active
        """

        with self._lock:
            # If already playing, we don't need to do anything
            if self._is_playing:
                return

            # We required to play a new data, lets load it
            if wav_data is not None:
                self.setWavData(wav_data)

            # Get a signal compatible with the device (may raise sd.PortAudioError)
            signal, self._play_rate = self._playbackSignal()

            # And now play!
            self._is_playing = True
            start_sample = int(start * self._play_rate)
            if end == -1:
                end_sample = signal.shape[0]
            else:
                end_sample = int(end * self._play_rate)

            # Reset position
            self._position = start_sample

            # Start stream in a new (daemon) thread so that it never blocks the application exit
            new_thread = threading.Thread(
                target=self.play_handler, args=(signal, start_sample, end_sample), name="spiny-player", daemon=True
            )
            new_thread.start()

    def pauseResume(self):
        # Update the pause status
        self._is_paused = not self._is_paused

    def stop(self):
        self._is_playing = False
        self._is_paused = False
        self._position = 0

    def toggleLoop(self):
        self._loop_activated = not self._loop_activated

    @property
    def signal(self) -> np.ndarray:
        """The loaded signal at its native sampling rate, shape (nb_samples, nb_channels)"""
        return self._wav

    @property
    def sampling_rate(self):
        """The native sampling rate of the loaded signal"""
        return self._sampling_rate

    @property
    def duration(self) -> float:
        """The duration of the loaded signal in seconds"""
        return self._wav.shape[0] / self._sampling_rate

    @property
    def filename(self):
        """The file the signal has been loaded from (None if the signal was given directly)"""
        return self._filename

    @property
    def device(self):
        """The output device index (None means the default output device)"""
        return self._device

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def loop_activated(self) -> bool:
        return self._loop_activated

    @property
    def volume(self) -> float:
        """The playback volume (between 0 and 1)"""
        return self._player_volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._player_volume = min(max(value, 0.0), 1.0)

    @property
    def position(self) -> float:
        """Current playback position in seconds (0 when stopped).

        This is a plain read of a value updated by the audio thread, so GUI code should poll it
        (e.g. with a QTimer) rather than being called back from the audio thread.
        """
        return self._position / self._play_rate

    def play_handler(self, signal, start, end):
        event = threading.Event()
        data = signal[:end, :]
        rate = self._play_rate
        self._last_status = None

        def callback(outdata, frames, time, status):
            # NOTE: this runs on the real-time audio thread: no GUI calls, no I/O
            if status:
                self._last_status = status

            chunksize = min(len(data) - self._position, frames)

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
                outdata[:chunksize] = data[self._position : self._position + chunksize] * self._player_volume
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
                channels=data.shape[1],
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
