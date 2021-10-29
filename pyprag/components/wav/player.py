#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module containing the player class and the player object which should be used. This object is accessible via "pygrad.audio.player.player"

LICENSE
"""

import pygame
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
    """Class encapsulating an audio player."""

    def __init__(self):
        self._is_playing = False
        self._is_paused = True

    def setWavData(self, wav_data):
        # First be sure everything is stopped
        if self._is_playing:
            self.stop()

        self._wav_data =(wav_data*np.iinfo(np.int16).max).astype(np.int16)
        self._sound = pygame.sndarray.make_sound(self._wav_data)

    def loadNewWav(self, wav_data, sr):
        # First be sure everything is stopped
        if self._is_playing:
            self.stop()

        self._sr = sr

        # Reinit the mixer
        pygame.mixer.quit()
        pygame.mixer.pre_init(self._sr, size=-16, channels=1)
        pygame.mixer.init(self._sr, size=-16, channels=1)

        # Load the wav data
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

        if wav_data is not None:
            self.setWavData(wav_data)

        if self._is_playing:
            return

        self._sound.play()
        self._is_playing = True


    def pauseResume(self):
        if self._is_paused:
            pygame.mixer.unpause()
        else:
            pygame.mixer.pause()

        self._is_paused = not self._is_paused

    def stop(self):
        self._sound.stop()
        self._is_playing = False
        self._is_paused = False

    def loop(self):
        if self._is_playing:
            return

        self._sound.play(-1)
        self._is_playing = True

player = Player()
