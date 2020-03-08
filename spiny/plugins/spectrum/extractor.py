import numpy as np
import librosa

from spiny.core import player


class SpectrumExtractor:
    def __init__(
        self,
        fft_length=2048,
        frameshift=5,
        framelength=5,
        window="hamming",
        cutoff=(400, 5000),
        threshold_amp=(-40, 0),
    ):
        self._spectrum = np.zeros((10, 10))

        # Define default parameters
        self._fft_length = fft_length
        self._frameshift = frameshift
        self._framelength = framelength
        self._window = window
        self._cutoff = cutoff
        self._threshold_amp = threshold_amp

    def extract(self):
        frameshift = int(0.001 * self._frameshift * player._sampling_rate)
        framelength = int(0.001 * self._framelength * player._sampling_rate)
        assert (
            framelength < self._fft_length
        ), f"The framelength ({framelength} samples) has to be less than the FFT length ({self._fft_length} samples)"

        sp = librosa.core.stft(
            player._wav[:, 0],
            n_fft=self._fft_length * 2,
            hop_length=frameshift,
            win_length=framelength,
            center=True,
            window=self._window,
        )

        # Extract Amplitude in the dB
        sp = np.abs(sp)
        sp = sp / np.max(sp)
        sp = librosa.amplitude_to_db(sp)

        # Transform and filter to make it ready for plotting
        sp = sp.T
        cutoff_coeff = (
            int(self._cutoff[0] * 2 * self._fft_length / (player._sampling_rate)),
            int(self._cutoff[1] * 2 * self._fft_length / (player._sampling_rate)),
        )
        sp = sp[:, cutoff_coeff[0] : cutoff_coeff[1]]
        sp[sp < self._threshold_amp[0]] = self._threshold_amp[0]
        sp[sp > self._threshold_amp[1]] = self._threshold_amp[1]

        self._spectrum = sp

        return self._spectrum
