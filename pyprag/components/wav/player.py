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
import pyaudio
import numpy as np
import time # NOTE: for active monitoring

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
        self._player = pyaudio.PyAudio()
        self._position = 0

    def setWavData(self, wav_data):
        # First be sure everything is stopped
        if self._is_playing:
            self.stop()

        self._data = wav_data

    def loadNewWav(self, wav_data, sr):
        # First be sure everything is stopped
        if self._is_playing:
            self.stop()

        # Load the wav data
        self._sr = sr
        self.setWavData(wav_data)


    def play(self, wav_data=None):
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
        print("ok, ready?")
        x = threading.Thread(target=self.play_handler(), args=())
        x.start()
        print("Thread has been started")

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
        print("Stopping required!")

    def toggleLoop(self):
        self._loop_activated = not self._loop_activated

    def set_position_handler(self, function):
        self._position_handler = function

    def _callback(self, in_data, frame_count, time_info, status):
        # Execute the position handler function if defined
        if self._position_handler is not None:
            self._position_handler(frame_count*self._position)

        # Prepare buffer
        cur_buffer = self._data[frame_count*self._position : frame_count*(self._position+1)]
        cur_buffer = cur_buffer.astype(np.float32).tobytes()

        # Prepare next position and move on
        self._position += 1
        return (cur_buffer, pyaudio.paContinue)

    def play_handler(self):

        # Initialize the player, the stream and the position
        self._player = pyaudio.PyAudio()
        self._stream = self._player.open(format=pyaudio.paFloat32,
                                         channels=1,
                                         rate=self._sr,
                                         output=True,
                                         stream_callback=self._callback)
        self._position = 0

        # Play
        while self._position == 0:
            print("start to play")
            # Start the playing
            self._stream.start_stream()

            # NOTE: active wait
            while self._stream.is_active():
                if not self._is_playing:
                    break
                time.sleep(0.1)

            # Dealing with the end: stop and reloop?
            self._stream.stop_stream()
            if self._loop_activated and self._is_playing:
                self._position = 0

        # Stop and clean everything
        print("ok I am over")
        self._stream.close()
        self._player.terminate()
        self._is_playing = False

player = Player()
