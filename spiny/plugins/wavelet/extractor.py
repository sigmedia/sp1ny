import logging

import numpy as np

# Wavelet part
# - acoustic features
from wavelet_prosody_toolkit.prosody_tools import energy_processing
from wavelet_prosody_toolkit.prosody_tools import f0_processing

# from wavelet_prosody_toolkit.prosody_tools import duration_processing

# - helpers
from wavelet_prosody_toolkit.prosody_tools import misc
from wavelet_prosody_toolkit.prosody_tools import smooth_and_interp

# - wavelet transform
from wavelet_prosody_toolkit.prosody_tools import cwt_utils


from spiny.core import player


class WaveletExtractor:
    def __init__(
        self,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._wavelet = np.zeros((10, 10))
        self._frameshift = 1 / 200.0

        self._num_scales = 34
        self._scale_distance = 0.25

        # Parameters controlled by the GUI (defaults reproduce the previous hard-coded behaviour)
        self._min_f0 = 50.0
        self._max_f0 = 400.0
        self._harmonics = 50.0
        self._voicing = 80.0
        self._weight_f0 = 1.0
        self._weight_energy = 1.0
        self._combination = "sum"  # "sum" or "product"

    def extract(self):
        self.energy = energy_processing.extract_energy(
            player.signal[:, 0],
            player.sampling_rate,
            200,  # self.configuration["energy"]["band_min"],
            5000,  # self.configuration["energy"]["band_max"],
            "rms",  # self.configuration["energy"]["calculation_method"],
        )
        self.energy_smooth = smooth_and_interp.peak_smooth(self.energy, 30, 3)  # FIXME: 30? 3?

        max_f0 = max(self._max_f0, 10.0)
        min_f0 = min(max_f0 - 1.0, self._min_f0)

        raw_pitch = f0_processing.extract_f0(
            player.signal[:, 0],
            player.sampling_rate,
            min_f0,
            max_f0,
            self._harmonics,
            self._voicing,
            "inst_freq",  # self.configuration["f0"]["pitch_tracker"],
        )

        try:
            self.pitch = f0_processing.process(raw_pitch)
        except Exception as ex:
            # f0_processing.process crashes if raw_pitch is all zeros (e.g. no voiced frame)
            self.logger.warning("F0 post-processing failed (%s), using the raw F0", ex)
            self.pitch = raw_pitch

        nb_frames = min(self.pitch.shape[0], self.energy.shape[0])
        pitch = self.pitch[:nb_frames]
        energy = self.energy_smooth[:nb_frames]
        if self._combination == "product":
            # Each feature contributes (normalised + weight); a null weight (or a flat signal) contributes 1
            params = np.ones(nb_frames)
            if self._weight_f0 > 0 and np.std(pitch) > 0:
                params *= misc.normalize_minmax(pitch) + self._weight_f0
            if self._weight_energy > 0 and np.std(energy) > 0:
                params *= misc.normalize_minmax(energy) + self._weight_energy
        else:
            params = misc.normalize_std(pitch) * self._weight_f0 + misc.normalize_std(energy) * self._weight_energy

        # if self.configuration["feature_combination"]["detrend"]:
        params = smooth_and_interp.remove_bias(params, 800)  # FIXME: 800?
        params = misc.normalize_std(params)

        self.cwt, self.scales, self.freqs = cwt_utils.cwt_analysis(
            params,
            mother_name="mexican_hat",  # self.configuration["wavelet"]["mother_wavelet"],
            period=3,  # self.configuration["wavelet"]["period"],
            first_freq=32,
            num_scales=self._num_scales,
            scale_distance=self._scale_distance,
            apply_coi=False,
        )

        # NOTE: magnitude rendering (np.abs) is not exposed yet
        self._wavelet = np.real(self.cwt).T

        return self._wavelet
