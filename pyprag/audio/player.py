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
class Player:
    """Class encapsulating an audio player."""

    def __init__(self, wav_data, sr):
        self.loadNewWav(wav_data, sr)

    def setWavData(self, wav_data):
        self._wav_data =(wav_data*np.iinfo(np.int16).max).astype(np.int16)
        self._sound = pygame.sndarray.make_sound(self._wav_data)

    def loadNewWav(self, wav_data, sr):
        self._sr = sr

        # Reinit the mixer
        pygame.mixer.quit()
        pygame.mixer.pre_init(self._sr, size=-16, channels=1)
        pygame.mixer.init(self._sr, size=-16, channels=1)

        # Load the wav data
        self.setWavData(wav_data)

        self._is_paused = False

    def play(self):
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
        self._sound.play()


    def pauseResume(self):
        if self._is_paused:
            pygame.mixer.unpause()
        else:
            pygame.mixer.pause()

        self._is_paused = not self._is_paused

    def stop(self):
        self._sound.stop()

    def loop(self):
        self._sound.play(-1)
