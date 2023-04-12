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


class WaveletExtractor:
    def __init__(
        self,
        wav_array=None,
        sampling_rate=None,
    ):
        self._wav_array = wav_array
        self._sampling_rate = sampling_rate
        self._wavelet = np.zeros((10, 10))
        self._frameshift = 1 / 200.0

        self._num_scales = 34
        self._scale_distance = 0.25

    def setWav(self, wav, sampling_rate):
        assert wav is not None
        self._wav_array = wav
        self._sampling_rate = sampling_rate

    def extract(self):
        self.energy = energy_processing.extract_energy(
            self._wav_array,
            self._sampling_rate,
            200,  # self.configuration["energy"]["band_min"],
            5000,  # self.configuration["energy"]["band_max"],
            "rms",  # self.configuration["energy"]["calculation_method"],
        )

        if True:  # self.configuration["energy"]["smooth_energy"]:
            self.energy_smooth = smooth_and_interp.peak_smooth(self.energy, 30, 3)  # FIXME: 30? 3?
        else:
            self.energy_smooth = self.energy

        min_f0 = 50.0  # float(str(self.min_f0.text()))
        max_f0 = 400.0  # float(str(self.max_f0.text()))
        max_f0 = np.max([max_f0, 10.0])
        min_f0 = np.min([max_f0 - 1.0, min_f0])

        raw_pitch = f0_processing.extract_f0(
            self._wav_array,
            self._sampling_rate,
            min_f0,
            max_f0,
            50.0,  # float(self.harmonics.value()),
            80.0,  # float(self.voicing.value()),
            "inst_freq",  # self.configuration["f0"]["pitch_tracker"],
        )

        # FIXME: fix errors, smooth and interpolate
        try:
            self.pitch = f0_processing.process(raw_pitch)
        except Exception as ex:
            raise ex
            # f0_processing.process crashes if raw_pitch is all zeros, kludge
            self.pitch = raw_pitch

        nb_frames = np.min([self.pitch.shape[0], self.energy.shape[0]])
        if False:  # self.mul_feats.isChecked():
            duration = np.ones(nb_frames)

            if float(1.0) > 0 and np.std(self.pitch) > 0:
                pitch = misc.normalize_minmax(self.pitch[:nb_frames]) + float(1.0)
            if float(1.0) > 0 and np.std(self.energy_smooth) > 0:
                energy = misc.normalize_minmax(self.energy_smooth[:nb_frames]) + float(1.0)
            # if float(self.wDuration.text()) > 0 and np.std(self.rate)>0:
            #     duration = misc.normalize_minmax(self.rate) + float(self.wDuration.text())
            duration *= 0

            params = pitch * energy * duration
        else:

            params = misc.normalize_std(self.pitch[:nb_frames]) * float(1.0) + misc.normalize_std(
                self.energy_smooth[:nb_frames]
            ) * float(
                1.0
            )  # + \
            # misc.normalize_std(self.rate) * float(self.wDuration.text())

        # if self.configuration["feature_combination"]["detrend"]:
        if True:
            params = smooth_and_interp.remove_bias(params, 800)  # FIXME: 800?

        params = misc.normalize_std(params)

        (self.cwt, self.scales, self.freqs) = cwt_utils.cwt_analysis(
            params,
            mother_name="mexican_hat",  # self.configuration["wavelet"]["mother_wavelet"],
            period=3,  # self.configuration["wavelet"]["period"],
            first_freq=32,
            num_scales=34,  # self.configuration["wavelet"]["num_scales"],
            scale_distance=0.25,  # self.configuration["wavelet"]["scale_distance"],
            apply_coi=False,
        )

        if False:  # self.configuration["wavelet"]["magnitude"]:
            # self.cwt = np.log(np.abs(self.cwt)+1.)
            self._wavelet = np.abs(self.cwt).T
        else:
            self._wavelet = np.real(self.cwt).T

        return self._wavelet
