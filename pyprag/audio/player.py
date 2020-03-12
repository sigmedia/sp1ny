#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module containing the player class and the player object which should be used. This object is accessible via "pygrad.audio.player.player"

LICENSE
"""

import sounddevice as sd

###############################################################################
# Classes
###############################################################################

class Player:
    """Class encapsulating an audio player.

    """

    def play(self, sig_array, sr, viewBox=None):
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
        sd.play(sig_array, sr)
        status = sd.wait()


###############################################################################
# Shared variables
###############################################################################

# The actual player
player = Player()
