import numpy as np
import parselmouth


class SpectrumPraatExtractor:
    def __init__(
        self,
        wav_array=None,
        sampling_rate=None,
    ):
        self._wav_array = wav_array
        self._sampling_rate = sampling_rate
        self._spectrum = np.zeros((10, 10))

    def setWav(self, wav, sampling_rate):
        assert wav is not None
        self._wav_array = wav
        self._sampling_rate = sampling_rate

    def extract(self):
        snd = parselmouth.Sound(self._wav_array, self._sampling_rate)
        sp = snd.to_spectrogram()
        self._spectrum = sp.values.T
        self._spectrum = 10 * np.log10(self._spectrum)
        self._frameshift = sp.get_time_step()
        self._cutoff = [sp.ymin, sp.ymax]
        return self._spectrum
