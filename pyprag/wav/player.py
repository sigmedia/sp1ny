#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module containing the player class and the player object which should be used.
    This object is accessible via "pygrad.audio.player.player"

LICENSE
"""

import threading

import sounddevice as sd

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

    def __init__(self, chunk_size=1024):
        self._is_playing = False
        self._is_paused = False
        self._loop_activated = False
        self._position_handler = None
        self._chunk_size = chunk_size
        self._position = 0
        self._position_handlers = []

    def setWavData(self, wav_data):
        # First be sure everything is stopped
        if self._is_playing:
            self.stop()

        self._data = wav_data
        if len(self._data.shape) < 2:
            self._data = np.expand_dims(self._data, axis=1)

    def loadNewWav(self, wav_data, sr):
        # First be sure everything is stopped
        if self._is_playing:
            self.stop()

        # Load the wav data
        self._sr = sr
        self.setWavData(wav_data)

    def play(self, wav_data=None, start=0, end=-1):
        """Play the signal given in parameters

        Parameters
        ----------
        sig_array : np.array
           The signal samples

        sr : int
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
        if end == -1:
            end = self._data.shape[0]
        else:
            start = int(start * self._sr)
            end = int(end * self._sr)

        new_thread = threading.Thread(target=self.play_handler, args=(start, end))
        new_thread.start()

    def pauseResume(self):
        # Update the pause status
        self._is_paused = not self._is_paused

        # Fix the stream
        if self._is_paused:
            self._stream.stop_stream()
        else:
            self._stream.start_stream()

    def stop(self):
        self._is_playing = False
        self._position = 0

    def toggleLoop(self):
        self._loop_activated = not self._loop_activated

    def add_position_handler(self, function):
        self._position_handlers.append(function)

    def play_handler(self, start, end):
        event = threading.Event()
        data = self._data[start:end, :]

        def callback(outdata, frames, time, status):
            if status:
                print(status)
            chunksize = min(len(data) - self._position, frames)
            outdata[:chunksize] = data[self._position : self._position + chunksize]
            if chunksize < frames:
                outdata[chunksize:] = 0
                raise sd.CallbackStop()
            self._position += chunksize

            # pos = self._position / self._sr
            # for f in self._position_handlers:
            #     f(pos)

        stream = sd.OutputStream(
            samplerate=self._sr, device=None, channels=data.shape[1], callback=callback, finished_callback=event.set
        )
        with stream:
            event.wait()  # Wait until playback is finished
            self._position = 0
            self._is_playing = 0


player = Player()