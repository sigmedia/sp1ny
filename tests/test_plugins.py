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
    from spiny.plugins.spectrum.extractor import SpectrogramSettings, SpectrumExtractor, get_window

    settings = SpectrogramSettings(frameshift=5, framelength=25, window="hann", max_frequency=4000)
    codes = SpectrumExtractor(settings).extract().codes.astype(int)

    n_fft = 4096  # fft_length() of a 400-sample window
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
