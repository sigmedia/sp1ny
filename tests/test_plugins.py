import time

import numpy as np
import pytest
from pyqtgraph.Qt import QtWidgets


def build_panel(controller, monkeypatch):  # used by the wavelet test
    holder = QtWidgets.QWidget()
    controller.setControlPanel(QtWidgets.QVBoxLayout(holder))
    monkeypatch.setattr(controller, "refresh", lambda: None)  # rendering is covered by the GUI test
    return holder


def wait_until(condition, timeout=20.0):
    """Process the Qt events until the condition is true (or the timeout expires)"""
    import time

    end = time.time() + timeout
    while not condition() and time.time() < end:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)
    return condition()


@pytest.fixture
def spectrogram(player, monkeypatch):
    """The spectrogram controller, displayed on a 10 s view: panel built, spectrogram extracted, refresh() counted"""
    from spiny.core.wav.visualisation import WavPlotWidget
    from spiny.plugins.spectrum import controller

    player.setWavData(np.sin(np.arange(16000 * 100) / 5).astype(np.float32))  # 100 s
    wav_plot = WavPlotWidget()
    wav_plot.setXRange(20, 30, padding=0)
    holder = QtWidgets.QWidget()  # keeps the panel alive
    controller.max_duration = 30
    controller.setControlPanel(QtWidgets.QVBoxLayout(holder))
    controller.setWavPlot(wav_plot)
    refreshes = []
    monkeypatch.setattr(controller, "refresh", lambda: refreshes.append(True))  # rendering: see test_gui.py
    controller.extract()
    refreshes.clear()
    yield controller, refreshes, wav_plot
    controller.release()


def wait_for_analysis(controller):
    """Wait until the delay has elapsed and the background analysis is finished"""
    assert wait_until(lambda: not controller._analysis_timer.isActive() and not controller._running)


def test_only_the_visible_part_is_computed(spectrogram):
    controller, _, _ = spectrogram
    result = controller._extractor.spectrogram
    assert result.start_time == pytest.approx(20) and result.codes.shape[0] == pytest.approx(2000, abs=2)
    assert result.covers(20, 30) and not result.covers(19, 30) and not result.covers(20, 31)


def test_panning_computes_the_new_part(spectrogram):
    controller, refreshes, wav_plot = spectrogram
    wav_plot.setXRange(50, 60, padding=0)
    wait_for_analysis(controller)
    assert len(refreshes) == 1 and controller._extractor.spectrogram.covers(50, 60)


def test_zooming_in_a_computed_part_computes_nothing(spectrogram):
    controller, refreshes, wav_plot = spectrogram
    wav_plot.setXRange(22, 25, padding=0)
    wait_for_analysis(controller)
    assert refreshes == []


def test_too_long_visible_part_shows_a_message_then_the_spectrogram(spectrogram):
    controller, refreshes, wav_plot = spectrogram
    wav_plot.setXRange(0, 100, padding=0)
    wait_for_analysis(controller)
    assert controller._extractor.spectrogram is None and refreshes == []
    assert "100.0 s" in controller.widget._message.text()

    wav_plot.setXRange(40, 70, padding=0)  # exactly the maximum
    wait_for_analysis(controller)
    assert controller.widget._message.text() == ""
    assert controller._extractor.spectrogram.covers(40, 70)


def test_max_duration_slider_applies_to_the_visible_part(spectrogram):
    controller, _, _ = spectrogram
    controller._max_duration.setValue(5)
    wait_for_analysis(controller)
    assert controller._extractor.spectrogram is None and "maximum of 5 s" in controller.widget._message.text()

    controller._max_duration.setValue(10)
    wait_for_analysis(controller)
    assert controller._extractor.spectrogram.covers(20, 30)


def test_too_long_visible_part_at_selection_computes_nothing(spectrogram):
    controller, _, wav_plot = spectrogram
    wav_plot.setXRange(0, 100, padding=0)
    controller.extract()
    assert controller._extractor.spectrogram is None and controller.widget._message.text() != ""


def test_display_settings_are_applied_without_analysis(spectrogram, monkeypatch):
    controller, refreshes, _ = spectrogram
    widget = controller.widget
    analyses = []
    monkeypatch.setattr(controller, "_scheduleAnalysis", lambda *args: analyses.append(True))

    controller._max_level.setValue(-10)
    controller._dynamic_range.setValue(30)
    controller._max_frequency.setValue(3000)
    controller._min_frequency.setValue(500)

    assert widget.db_range == (-40, -10) and widget.frequency_range == (500, 3000)
    assert widget._plotItem.getViewBox().viewRange()[1] == pytest.approx([500, 3000])
    assert analyses == [] and refreshes == []

    controller._min_frequency.setValue(3000)  # crossing the other bound pushes it
    assert widget.frequency_range == (3000, 3050)


def test_analysis_settings_update_the_spectrogram_in_the_background(spectrogram):
    controller, refreshes, _ = spectrogram
    controller._window_length.setValue(10)
    controller._window_length.setValue(12)  # a second change before the delay: a single analysis
    assert controller._analysis_timer.interval() == controller.ANALYSIS_DELAY_MS  # not the value of the slider
    wait_for_analysis(controller)
    assert len(refreshes) == 1
    assert controller._extractor.settings.framelength == 12


def test_outdated_analyses_are_dropped(spectrogram):
    controller, refreshes, _ = spectrogram
    controller._time_step.setValue(10)
    controller._analysis_timer.timeout.emit()  # start now, without waiting for the delay
    controller.release()  # e.g. another plugin is selected while the analysis is running
    assert wait_until(lambda: not controller._running)
    assert refreshes == [] and controller._extractor.spectrogram is None


def test_spectrum_of_silence_is_the_lowest_level(player):
    from spiny.plugins.spectrum.extractor import SpectrumExtractor

    player.setWavData(np.zeros(16000, dtype=np.float32))
    codes = SpectrumExtractor().extract().codes
    assert codes.dtype == np.uint8 and (codes == 0).all()


def test_full_scale_sine_is_at_0_db_whatever_the_analysed_part(player):
    from spiny.plugins.spectrum.extractor import SpectrumExtractor

    # The reference is the peak of the whole signal: analysing the quiet part alone does not raise its level
    signal = 0.5 * np.sin(2 * np.pi * 1000 * np.arange(32000) / 16000).astype(np.float32)
    signal[:16000] *= 0.01
    player.setWavData(signal)
    codes = SpectrumExtractor().extract(1.2, 1.8).codes
    assert codes.max() == 255
    quiet = SpectrumExtractor().extract(0.2, 0.8).codes
    assert quiet.max() == pytest.approx(128, abs=1)  # 40 dB lower: (80 - 40) / 80 × 255


def test_spectrum_matches_librosa(player):
    """The numpy STFT reproduces librosa's stft + amplitude_to_db (up to one 8-bit code)"""
    librosa = pytest.importorskip("librosa")
    from spiny.plugins.spectrum.extractor import SpectrogramSettings, SpectrumExtractor, fft_length, get_window

    settings = SpectrogramSettings(frameshift=5, framelength=25, window="hann", max_frequency=4000)
    codes = SpectrumExtractor(settings).extract().codes.astype(int)

    n_fft = fft_length(400)
    signal = player.signal[:, 0]
    reference = np.abs(signal).max() * get_window("hann", 400, n_fft).sum() / 2
    sp = np.abs(librosa.stft(signal, n_fft=n_fft, hop_length=80, win_length=400, window="hann", center=True))
    sp = librosa.amplitude_to_db(sp, ref=reference, top_db=None).T[:, : int(4000 * n_fft / player.sampling_rate) + 1]
    expected = np.rint((np.clip(sp, -80, 0) + 80) * 255 / 80).astype(int)
    assert codes.shape == expected.shape
    assert np.abs(codes - expected).max() <= 1


def test_visible_part_matches_the_whole_analysis(player):
    from spiny.plugins.spectrum.extractor import SpectrumExtractor

    extractor = SpectrumExtractor()
    whole = extractor.extract().codes
    part = extractor.extract(1.0, 2.0)
    first = round(part.start_time / part.frame_duration)
    assert (part.codes == whole[first : first + part.codes.shape[0]]).all()


@pytest.mark.parametrize(
    "settings, error",
    [
        ({"window": "nope"}, "supported windows"),
        ({"frameshift": 0.01}, "time step"),
        ({"max_frequency": 0}, "positive"),
    ],
)
def test_spectrum_rejects_invalid_settings(player, settings, error):
    from spiny.plugins.spectrum.extractor import SpectrogramSettings, SpectrumExtractor

    with pytest.raises(ValueError, match=error):
        SpectrumExtractor(SpectrogramSettings(**settings)).extract()


def test_praat_spectrum_of_silence(player):
    pytest.importorskip("parselmouth")
    from spiny.plugins.spectrum_praat.extractor import SpectrumPraatExtractor

    player.setWavData(np.zeros(16000, dtype=np.float32))
    spectrum = SpectrumPraatExtractor().extract()
    assert spectrum.dtype == np.uint8 and spectrum.shape[0] > 0


def test_praat_spectrum_chunks_match_the_full_analysis(player):
    """Chunking does not change the spectrogram (apart from the frame grid, shifted by < half a step)"""
    parselmouth = pytest.importorskip("parselmouth")
    from spiny.plugins.spectrum_praat.extractor import SpectrumPraatExtractor

    chunked = SpectrumPraatExtractor(chunk_duration=0.5).extract().astype(int)
    full = SpectrumPraatExtractor(chunk_duration=1000).extract().astype(int)
    reference = parselmouth.Sound(player.signal[:, 0].astype(float), player.sampling_rate).to_spectrogram()
    assert full.shape == (reference.values.shape[1], reference.values.shape[0])
    assert abs(chunked.shape[0] - full.shape[0]) <= 8  # at most one frame per chunk boundary
    n = min(chunked.shape[0], full.shape[0])
    assert np.median(np.abs(chunked[:n] - full[:n])) <= 4


def test_wavelet_panel_can_be_built_twice(player, no_dialogs, monkeypatch):
    pytest.importorskip("wavelet_prosody_toolkit.prosody_tools")
    from spiny.plugins.wavelet import controller

    first = build_panel(controller, monkeypatch)  # noqa: F841
    second = build_panel(controller, monkeypatch)  # noqa: F841 (used to raise "QListWidget is not callable")
    controller.min_f0.setText("500")
    controller.max_f0.setText("100")
    controller.extract()
    assert len(no_dialogs) == 1


def test_raw_data_dimension_is_validated(qapp, tmp_path):
    from spiny.raw_data.extractor import RawDataExtractor

    np.arange(10, dtype=np.float32).tofile(tmp_path / "c.bin")
    extractor = RawDataExtractor()
    for dimension in (0, 3):
        extractor.loadCoefficientFile(str(tmp_path / "c.bin"), dimension, 5)
        with pytest.raises(ValueError):
            extractor.extract()
    extractor.loadCoefficientFile(str(tmp_path / "c.bin"), -5, 5)
    data = extractor.extract()
    assert data.shape == (2, 5) and isinstance(data.base, np.memmap) and data[1, 0] == 5
    extractor.loadCoefficientFile(str(tmp_path / "c.bin"), 2, 5)
    assert extractor.extract()[:, 1].tolist() == [5, 6, 7, 8, 9]
    (tmp_path / "empty.bin").write_bytes(b"")
    extractor.loadCoefficientFile(str(tmp_path / "empty.bin"), -5, 5)
    assert extractor.extract().shape == (0, 5)


def test_duplicate_plugin_names_are_rejected(qapp):
    from spiny.core import DataController, plugin_entry_dict, register_plugin

    name = "dummy-test-plugin"
    try:
        register_plugin(DataController(name, None, None))
        with pytest.raises(ValueError):
            register_plugin(DataController(name, None, None))
    finally:
        plugin_entry_dict.pop(name, None)  # do not leak the dummy plugin into the other tests


def test_reusing_a_previous_part_gives_the_same_frames(player, monkeypatch):
    from spiny.plugins.spectrum import extractor

    signal = np.sin(np.arange(16000 * 20) ** 1.2 / 500).astype(np.float32)
    settings = extractor.SpectrogramSettings()
    expected = extractor.compute_spectrogram(signal, 16000, settings, 5.0, 12.0)
    previous = extractor.compute_spectrogram(signal, 16000, settings, 7.0, 10.0)

    computed = []
    stft = extractor.stft_magnitude
    monkeypatch.setattr(
        extractor,
        "stft_magnitude",
        lambda s, first, last, *args: computed.append(last - first) or stft(s, first, last, *args),
    )
    result = extractor.compute_spectrogram(signal, 16000, settings, 5.0, 12.0, previous)
    assert result.start_time == expected.start_time
    assert np.array_equal(result.codes, expected.codes)
    assert sum(computed) == expected.codes.shape[0] - previous.codes.shape[0]

    # Nothing in common, and nothing to compute at all
    far = extractor.compute_spectrogram(signal, 16000, settings, 15.0, 18.0)
    assert np.array_equal(extractor.compute_spectrogram(signal, 16000, settings, 5.0, 12.0, far).codes, expected.codes)
    computed.clear()
    same = extractor.compute_spectrogram(signal, 16000, settings, 5.0, 12.0, expected)
    assert np.array_equal(same.codes, expected.codes) and not computed


def test_moving_all_the_time_does_not_delay_the_analysis(spectrogram):
    controller, _, _ = spectrogram
    controller._scheduleAnalysis()
    time.sleep(0.015)
    remaining = controller._analysis_timer.remainingTime()
    controller._scheduleAnalysis()  # a new mouse event during a drag
    assert controller._analysis_timer.remainingTime() <= remaining


def test_small_pans_are_covered_by_the_margin(spectrogram):
    controller, refreshes, wav_plot = spectrogram
    wav_plot.setXRange(40, 50, padding=0)
    wait_for_analysis(controller)
    result = controller._extractor.spectrogram
    assert result.covers(35, 55)
    refreshes.clear()
    wav_plot.setXRange(41, 51, padding=0)
    wait_for_analysis(controller)
    assert not refreshes and controller._extractor.spectrogram is result


PRAAT_CONFIGURATIONS = [
    {},
    {"framelength": 30.0, "frameshift": 5.0, "frequency_step": 10.0},
    {"framelength": 5.0, "frameshift": 1.0, "max_frequency": 8000.0},
    {"framelength": 10.0, "frameshift": 3.3, "max_frequency": 3000.0, "frequency_step": 50.0},
]


@pytest.mark.parametrize("configuration", PRAAT_CONFIGURATIONS)
@pytest.mark.parametrize("rate", [16000, 44100])
def test_praat_method_replicates_praat(player, configuration, rate):
    parselmouth = pytest.importorskip("parselmouth")
    from spiny.plugins.spectrum.extractor import SpectrogramSettings, compute_spectrogram

    if rate == 16000:
        signal = player.signal[:, 0]
    else:
        signal = np.random.default_rng(0).normal(0, 0.1, rate * 2).astype(np.float32)
    defaults = {"framelength": 5.0, "frameshift": 2.0, "max_frequency": 5000.0, "frequency_step": 20.0}
    values = {**defaults, **configuration}
    slice_ = compute_spectrogram(signal, rate, SpectrogramSettings(method="praat", **values))

    reference = parselmouth.Sound(signal.astype(np.float64), rate).to_spectrogram(
        window_length=values["framelength"] / 1000,
        maximum_frequency=values["max_frequency"],
        time_step=values["frameshift"] / 1000,
        frequency_step=values["frequency_step"],
    )
    power = reference.values.T
    decibels = 10 * np.log10(np.maximum(power, 1e-30) / power.max())
    expected = np.rint((np.clip(decibels, -80, 0) + 80) * 255 / 80)
    assert slice_.codes.shape == power.shape
    differences = np.abs(slice_.codes.astype(int) - expected)
    if rate == 16000:
        assert differences.max() <= 1
    else:
        # NOTE: when a frame falls exactly between two samples, the last bits of the time decide which one comes first
        assert (differences <= 1).mean() > 0.97
    assert slice_.start_time == pytest.approx(reference.x1 - reference.dx / 2)
    assert slice_.frame_duration == pytest.approx(reference.dx)


def test_visible_part_of_the_praat_method_is_the_same_as_the_whole(player):
    from spiny.plugins.spectrum.extractor import SpectrogramSettings, compute_spectrogram

    signal, rate = player.signal[:, 0], player.sampling_rate
    settings = SpectrogramSettings(method="praat", framelength=5.0, frameshift=2.0)
    whole = compute_spectrogram(signal, rate, settings)
    part = compute_spectrogram(signal, rate, settings, 1.0, 2.0)
    first = round((part.start_time - whole.start_time) / part.frame_duration)
    assert np.array_equal(part.codes, whole.codes[first : first + part.codes.shape[0]])

    # With the frames of a part given, the same frames come out
    wider = compute_spectrogram(signal, rate, settings, 0.5, 2.5, part)
    first = round((wider.start_time - whole.start_time) / wider.frame_duration)
    assert np.array_equal(wider.codes, whole.codes[first : first + wider.codes.shape[0]])


def test_praat_method_refuses_a_signal_shorter_than_its_window(player):
    from spiny.plugins.spectrum.extractor import SpectrogramSettings, compute_spectrogram

    with pytest.raises(ValueError, match="shorter"):
        compute_spectrogram(np.zeros(10, dtype=np.float32), 16000, SpectrogramSettings(method="praat"))


def test_panel_goes_to_the_defaults_of_praat(spectrogram):
    controller, _, _ = spectrogram
    controller._method.setCurrentIndex(controller._method.findData("praat"))
    settings = controller._panelSettings()
    assert (settings.method, settings.framelength, settings.frameshift) == ("praat", 5, 2)
    assert settings.frequency_step == 20 and settings.max_frequency == 5000
    assert controller._dynamic_range.value() == 70 and controller._max_level.value() == 0
    assert not controller._analysis_layout.isRowVisible(controller._window)
    assert controller._analysis_layout.isRowVisible(controller._frequency_step)
    wait_for_analysis(controller)
    assert controller._extractor.settings == settings

    controller._method.setCurrentIndex(controller._method.findData("standard"))
    assert controller._panelSettings().framelength == 30
    assert controller._analysis_layout.isRowVisible(controller._window)
    wait_for_analysis(controller)
