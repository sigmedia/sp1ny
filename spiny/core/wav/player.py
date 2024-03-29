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
"""

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

    For now it relies on pyaudio as qmultimedia is not available in the pyside package from conda
    """

    def __init__(self, chunk_size=1024, filename=None):
        self._is_playing = False
        self._is_paused = False
        self._loop_activated = False
        self._position_handler = None
        self._chunk_size = chunk_size
        self._position = 0
        self._player_volume = 1.0
        self._position_handlers = []
        self._filename = None

        # Define devices and current device being the default one
        self._device = sd.query_hostapis()[0].get("default_" + "output".lower() + "_device")
        self._device_samplerate = sd.query_devices()[self._device]['default_samplerate']

        if filename is not None:
            self.loadNewWav(filename)

    def setWavData(self, wav_data):
        # First be sure everything is stopped
        if self._is_playing:
            self.stop()

        self._wav = wav_data
        if len(self._wav.shape) < 2:
            self._wav = np.expand_dims(self._wav, axis=1)

    def loadNewWav(self, filename):
        # First be sure everything is stopped
        if self._is_playing:
            self.stop()

        # Load the wav data
        self._filename = filename
        wav_data, self._sampling_rate = librosa.core.load(filename, sr=self._device_samplerate)
        self.setWavData(wav_data)

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

        # If already playing, we don't need to do anything
        if self._is_playing:
            return

        # We required to play a new data, lets load it
        if wav_data is not None:
            self.setWavData(wav_data)

        # And now play!
        self._is_playing = True
        start_sample = int(start * self._sampling_rate)
        if end == -1:
            end_sample = self._wav.shape[0]
        else:
            end_sample = int(end * self._sampling_rate)

        # Reset position
        self._position = start_sample

        # Start stream in a new thread
        new_thread = threading.Thread(target=self.play_handler, args=(start_sample, end_sample))
        new_thread.start()

    def pauseResume(self):
        # Update the pause status
        self._is_paused = not self._is_paused

    def stop(self):
        self._is_playing = False
        self._position = 0

    def toggleLoop(self):
        self._loop_activated = not self._loop_activated

    def add_position_handler(self, function):
        self._position_handlers.append(function)

    def play_handler(self, start, end):
        event = threading.Event()
        data = self._wav[:end, :]

        def callback(outdata, frames, time, status):
            if status:
                print(status)

            chunksize = min(len(data) - self._position, frames)

            # Update position of scrub bars
            pos = self._position / self._sampling_rate
            for f in self._position_handlers:
                f(pos)

            # If stream is paused, keep open but output zeros
            # position is not updated so can resume from same frame
            if self._is_paused:
                outdata[:chunksize] = np.zeros((chunksize, 1))
            # Stream Stopped
            elif not self._is_playing:
                outdata[:chunksize] = np.zeros((chunksize, 1))
                self._position = start
                raise sd.CallbackStop()
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

        sd.check_output_settings(
            samplerate=self._sampling_rate,
            device=self._device,
            channels=data.shape[1],
        )
        self._stream = sd.OutputStream(
            samplerate=self._sampling_rate,
            device=self._device,
            channels=data.shape[1],
            callback=callback,
            finished_callback=event.set,
        )
        with self._stream:
            event.wait()  # Wait until playback is finished
            self._position = 0
            self._is_playing = False
            # reset scrub bars
            for f in self._position_handlers:
                f(0)


player = Player()
