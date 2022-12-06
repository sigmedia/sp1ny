import numpy as np
import librosa


class SpectrumExtractor:
    def __init__(
        self,
        wav_array,
        sampling_rate,
        fft_len=2048,
        frameshift=0.005,
        framelength=0.005,
        window="hamming",
        cutoff=(400, 5000),
        threshold_amp=(-40, 0),
    ):
        self._wav_array = wav_array
        self._sampling_rate = sampling_rate

        # Define default parameters
        self._fft_len = fft_len
        self._frameshift = frameshift
        self._framelength = framelength
        self._window = window
        self._cutoff = cutoff
        self._threshold_amp = threshold_amp

        # Extract Default
        self.extract()

    def extract(self):
        frameshift = int(self._frameshift * self._sampling_rate)
        framelength = int(self._framelength * self._sampling_rate)
        assert (
            framelength < self._fft_len
        ), f"The framelength ({framelength} samples) has to be less than the FFT length ({self._fft_len} samples)"

        sp = librosa.core.stft(
            self._wav_array,
            n_fft=self._fft_len * 2,
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
            int(self._cutoff[0] * 2 * self._fft_len / (self._sampling_rate)),
            int(self._cutoff[1] * 2 * self._fft_len / (self._sampling_rate)),
        )
        sp = sp[:, cutoff_coeff[0] : cutoff_coeff[1]]
        sp[sp < self._threshold_amp[0]] = self._threshold_amp[0]
        sp[sp > self._threshold_amp[1]] = self._threshold_amp[1]

        self._spectrum = sp

        return self._spectrum
