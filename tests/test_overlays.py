import numpy as np
import pytest

from conftest import EXAMPLES
from spiny.core.overlay import signal_frames
from spiny.overlays.f0.extractor import F0Settings, compute_f0
from spiny.overlays.formants.extractor import FormantSettings, compute_formants

RATE = 16000


def resonant_vowel(formants, f0=120.0, seconds=1.0, rate=RATE):
    """A pulse train through resonators of known frequencies"""
    signal = np.zeros(int(seconds * rate))
    signal[:: int(rate / f0)] = 1.0
    for frequency in formants:
        radius = np.exp(-np.pi * 80.0 / rate)
        a1, a2 = -2 * radius * np.cos(2 * np.pi * frequency / rate), radius**2
        output = np.zeros_like(signal)
        for n in range(signal.size):
            output[n] = signal[n] - a1 * output[n - 1] - a2 * output[n - 2] if n > 1 else signal[n]
        signal = output
    return (signal / np.abs(signal).max() * 0.5).astype(np.float32)


def nb_frames(signal, rate=RATE, step=5.0):
    return signal.shape[0] // round(step * rate / 1000) + 1


def test_frames_are_centred_and_padded_with_zeros():
    signal = np.arange(1, 101, dtype=np.float32)
    frames = signal_frames(signal, 0, 3, 10, 4)
    assert frames[0].tolist() == [0, 0, 1, 2]
    assert frames[1].tolist() == [9, 10, 11, 12]
    last = signal_frames(signal, 10, 11, 10, 4)[0]
    assert last.tolist() == [99, 100, 0, 0]


@pytest.mark.parametrize("formants", [(500, 1500, 2500), (450, 1900, 2800), (700, 1200, 2600)])
def test_formants_of_a_synthetic_vowel(formants):
    signal = resonant_vowel(formants)
    settings = FormantSettings(nb_formants=3)
    middle = compute_formants(signal, RATE, settings, 0, nb_frames(signal))[50:-50]
    # NOTE: linear prediction pulls F1 towards the harmonics of such a clean signal, as Praat does
    assert np.nanmedian(middle[:, 0]) == pytest.approx(formants[0], rel=0.35)
    for index in (1, 2):
        assert np.nanmedian(middle[:, index]) == pytest.approx(formants[index], rel=0.05)


def test_silence_has_no_formants_and_no_f0():
    silence = np.zeros(RATE, dtype=np.float32)
    assert np.isnan(compute_formants(silence, RATE, FormantSettings(), 0, 100)).all()
    assert np.isnan(compute_f0(silence, RATE, F0Settings(), 0, 100)).all()


def test_quiet_parts_have_no_formants():
    signal = resonant_vowel((500, 1500, 2500))
    signal[RATE // 2 :] *= 1e-4
    tracks = compute_formants(signal, RATE, FormantSettings(), 0, nb_frames(signal))
    assert np.isfinite(tracks[20:80, 0]).all() and np.isnan(tracks[120:, 0]).all()


def test_formants_do_not_depend_on_how_the_frames_are_grouped():
    signal = resonant_vowel((500, 1500, 2500))
    whole = compute_formants(signal, RATE, FormantSettings(), 0, 100)
    parts = np.concatenate([compute_formants(signal, RATE, FormantSettings(), a, a + 25) for a in range(0, 100, 25)])
    assert np.allclose(whole, parts, equal_nan=True, atol=0.5)


@pytest.mark.parametrize("rate", [8000, 16000, 48000])
def test_formants_at_every_rate_and_above_nyquist(rate):
    signal = resonant_vowel((500, 1500), rate=rate)
    tracks = compute_formants(signal, rate, FormantSettings(), 0, nb_frames(signal, rate))
    assert np.nanmedian(tracks[50:-50, 0]) == pytest.approx(500, rel=0.08)


@pytest.mark.parametrize("f0", [90.0, 120.0, 220.0, 400.0])
def test_f0_of_a_pulse_train(f0):
    signal = resonant_vowel((500, 1500), f0=f0)
    track = compute_f0(signal, RATE, F0Settings(), 0, nb_frames(signal))[:, 0]
    middle = track[50:-50]
    assert np.isfinite(middle).mean() > 0.95
    assert np.nanmedian(middle) == pytest.approx(RATE / int(RATE / f0), rel=0.01)


def test_noise_is_not_voiced():
    noise = np.random.default_rng(0).normal(0, 0.1, RATE).astype(np.float32)
    track = compute_f0(noise, RATE, F0Settings(), 0, nb_frames(noise))
    assert np.isfinite(track).mean() < 0.05


def test_f0_stays_in_the_range():
    signal = resonant_vowel((500, 1500), f0=200.0)
    settings = F0Settings(min_f0=100.0, max_f0=300.0)
    track = compute_f0(signal, RATE, settings, 0, nb_frames(signal))
    assert np.nanmin(track) >= 100 and np.nanmax(track) <= 300


def test_f0_grouped_by_chunks_is_continuous():
    signal = resonant_vowel((500, 1500), f0=150.0)
    whole = compute_f0(signal, RATE, F0Settings(), 0, 180)
    parts = np.concatenate([compute_f0(signal, RATE, F0Settings(), a, a + 45) for a in range(0, 180, 45)])
    both = np.isfinite(whole) & np.isfinite(parts)
    assert (np.isfinite(whole) == np.isfinite(parts)).mean() > 0.97
    assert np.allclose(whole[both], parts[both], rtol=0.01)


@pytest.mark.parametrize("filename", ["arctic_a0002.wav", "arctic_as.wav"])
def test_real_speech_agrees_with_praat(filename):
    parselmouth = pytest.importorskip("parselmouth")
    import soundfile as sf

    signal, rate = sf.read(EXAMPLES / filename, dtype="float32")
    frames = int(signal.shape[0] / rate / 0.005)
    times = np.arange(frames) * 0.005
    sound = parselmouth.Sound(signal.astype(np.float64), rate)

    pitch = sound.to_pitch(time_step=0.005, pitch_floor=75, pitch_ceiling=500)
    reference = np.array([pitch.get_value_at_time(t) for t in times])
    f0 = compute_f0(signal, rate, F0Settings(), 0, frames)[:, 0]
    both = np.isfinite(reference) & np.isfinite(f0)
    assert np.median(np.abs(reference[both] - f0[both])) < 1
    assert (np.abs(reference[both] - f0[both]) / reference[both] > 0.2).mean() < 0.02
    assert (np.isfinite(reference) == np.isfinite(f0)).mean() > 0.85

    burg = sound.to_formant_burg(time_step=0.005, max_number_of_formants=5, maximum_formant=5500, window_length=0.025)
    formants = compute_formants(signal, rate, FormantSettings(), 0, frames)
    voiced = np.isfinite(reference)
    for index in range(3):
        expected = np.array([burg.get_value_at_time(index + 1, t) for t in times])
        kept = voiced & np.isfinite(expected) & np.isfinite(formants[:, index])
        errors = np.abs(expected[kept] - formants[kept, index])
        assert np.median(errors) < 25 and np.quantile(errors, 0.9) < 100
