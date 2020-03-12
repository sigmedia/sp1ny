#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module containing classes related to spectrum analysis

LICENSE
"""

# Base line imports
import numpy as np
import librosa


###############################################################################
# Classes
###############################################################################

class SpectrumAnalysis:
    """Spectrum analysis class

    Attributes
    ----------
    wav : tuple(np.array, int)
        The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate

    fft_len : int
        The length of the FFT

    frameshift : float
        The frameshift (in seconds)

    Spectrum : np.array(nb_frames, fft_len)
        The matrix containing the spectrum
    """

    def __init__(self, wav, fft_len=512, frameshift=0.005):
        """
        Parameters
        ----------
        wav : tuple(np.array, int)
            The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate

        fft_len : int, optional
            The length of the FFT (default=512)

        frameshift : float, optional
            The frameshift (in seconds) (default=0.005)

        """
        self.wav = wav
        self.fft_len = fft_len
        self.frameshift = frameshift
        self.spectrum = None

        self.__process()

    def __process(self):
        """Method which compute the spectrum and fill the object attributes

        """
        # Compute spectrogram
        frameshift = int(self.frameshift * self.wav[1])
        sp = librosa.core.stft(self.wav[0],
                               n_fft=self.fft_len*2, hop_length=frameshift,
                               center=False, window="hamming")


        # sp = librosa.feature.melspectrogram(self.wav[0],
        #                                     n_fft=self.fft_len*2, n_mels=self.fft_len, hop_length=frameshift,
        #                                     center=False, window="hamming")

        # Post processing
        sp = np.abs(sp)
        sp = sp / np.max(sp)
        sp = librosa.amplitude_to_db(abs(sp))

        # tata
        sp = sp.T
        sp = sp[:, :self.fft_len] # Get rid of of the +1 coefficient

        self.spectrum = sp