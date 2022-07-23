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

    def __init__(self, wav, fft_len=512, frameshift=0.05, window="blackman", mel_scale=False):
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
        self._wav = wav
        self._fft_len = fft_len
        self._frameshift = frameshift
        self._window = window
        self._spectrum = None
        self._mel_scale = mel_scale

        self.__process()

    def __process(self):
        """Method which compute the spectrum and fill the object attributes"""
        # Compute spectrogram
        frameshift = int(self._frameshift * self._wav[1])
        framelength = int(0.045 * self._wav[1])
        self._fft_len = 1024

        if self._mel_scale:
            sp = librosa.feature.melspectrogram(
                self._wav[0],
                n_fft=self._fft_len * 2,
                n_mels=self._fft_len,
                hop_length=frameshift,
                center=False,
                window=self._window,
            )
        else:
            sp = librosa.core.stft(
                self._wav[0],
                n_fft=self._fft_len * 2,
                hop_length=frameshift,
                win_length=framelength,
                center=False,
                window=self._window,
            )

        # Post processing
        sp = np.abs(sp)
        sp = sp / np.max(sp)
        # sp = np.log2(abs(sp))
        sp = librosa.amplitude_to_db(abs(sp))

        # tata
        sp = sp.T
        sp = sp[:, : self._fft_len]  # Get rid of of the +1 coefficient

        sp[sp < -70] = -70
        # sp = sp[:, :int(0.6*self._fft_len)]
        self._spectrum = sp
