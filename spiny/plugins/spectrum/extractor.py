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
        """Compute the spectrogram of the loaded signal

        Raises
        ------
        ValueError
            if the parameters are inconsistent
        """
        frameshift = int(0.001 * self._frameshift * player.sampling_rate)
        framelength = int(0.001 * self._framelength * player.sampling_rate)
        if frameshift < 1:
            raise ValueError(f"The frameshift ({self._frameshift} ms) is shorter than one sample")
        if not 0 < framelength < self._fft_length:
            raise ValueError(
                f"The framelength ({framelength} samples) has to be positive and less than "
                + f"the FFT length ({self._fft_length} samples)"
            )
        if not 0 <= self._cutoff[0] < self._cutoff[1]:
            raise ValueError(f"The frequency range must satisfy 0 <= min < max (got {self._cutoff})")
        if not self._threshold_amp[0] < self._threshold_amp[1]:
            raise ValueError(f"The amplitude range must satisfy min < max (got {self._threshold_amp})")

        try:
            sp = librosa.core.stft(
                player.signal[:, 0],
                n_fft=self._fft_length * 2,
                hop_length=frameshift,
                win_length=framelength,
                center=True,
                window=self._window,
            )
        except librosa.util.exceptions.ParameterError as ex:
            raise ValueError(str(ex)) from ex

        # Extract Amplitude in the dB (a silent signal must not lead to a division by zero)
        sp = np.abs(sp)
        sp = sp / max(np.max(sp), np.finfo(sp.dtype).tiny)
        sp = librosa.amplitude_to_db(sp)

        # Transform and filter to make it ready for plotting
        sp = sp.T
        cutoff_coeff = (
            int(self._cutoff[0] * 2 * self._fft_length / (player.sampling_rate)),
            int(self._cutoff[1] * 2 * self._fft_length / (player.sampling_rate)),
        )
        sp = sp[:, cutoff_coeff[0] : cutoff_coeff[1]]
        sp[sp < self._threshold_amp[0]] = self._threshold_amp[0]
        sp[sp > self._threshold_amp[1]] = self._threshold_amp[1]

        self._spectrum = sp

        return self._spectrum
