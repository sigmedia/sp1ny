#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

LICENSE
    This script is in the public domain, free from copyrights or restrictions.
    Created:  6 March 2020
"""

# Linear algebra
import numpy as np

import librosa

class SpectrumAnalysis:
    def __init__(self, wav, fft_len=512, frameshift=0.005):
        self.wav = wav
        self.fft_len = fft_len
        self.frameshift = frameshift

        self.spectrum = None

    def analyze(self):
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
