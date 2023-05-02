import numpy as np
import parselmouth


from spiny.core import player


class SpectrumPraatExtractor:
    def __init__(
        self,
    ):
        self._spectrum = np.zeros((10, 10))

    def extract(self):
        snd = parselmouth.Sound(player._wav[:, 0], player._sampling_rate)
        sp = snd.to_spectrogram()
        self._spectrum = sp.values.T
        self._spectrum = 10 * np.log10(self._spectrum)
        self._frameshift = sp.get_time_step()
        self._cutoff = [sp.ymin, sp.ymax]
        return self._spectrum
