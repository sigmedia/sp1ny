import numpy as np
import pytest
from pyqtgraph.Qt import QtWidgets


def build_panel(controller, monkeypatch):
    holder = QtWidgets.QWidget()
    controller.setControlPanel(QtWidgets.QVBoxLayout(holder))
    monkeypatch.setattr(controller, "refresh", lambda: None)  # rendering is covered by the GUI test
    return holder


def test_spectrum_parameters_are_validated(player, no_dialogs, monkeypatch):
    from spiny.plugins.spectrum import controller

    holder = build_panel(controller, monkeypatch)  # noqa: F841 (keeps the panel alive)
    controller.extract()
    assert controller._extractor._spectrum.ndim == 2

    controller._wFramelength.setValue(500)  # longer than the FFT
    controller.extract()
    controller._wFramelength.setValue(30)
    controller._wMinAmp.setValue(0)  # empty amplitude range
    controller.extract()
    controller._wMinAmp.setValue(-70)
    assert len(no_dialogs) == 2


def test_spectrum_of_silence_is_the_lowest_level(player):
    from spiny.plugins.spectrum.extractor import SpectrumExtractor

    player.setWavData(np.zeros(16000, dtype=np.float32))
    spectrum = SpectrumExtractor().extract()
    assert spectrum.dtype == np.uint8 and (spectrum == 0).all()


def test_spectrum_matches_librosa(player):
    """The numpy STFT reproduces the former librosa-based computation (up to one 8-bit code)"""
    librosa = pytest.importorskip("librosa")
    from spiny.plugins.spectrum.extractor import SpectrumExtractor

    extractor = SpectrumExtractor(fft_length=1024, frameshift=5, framelength=25, window="hann", cutoff=(100, 4000))
    spectrum = extractor.extract().astype(int)

    sr, n_fft = player.sampling_rate, 2048
    sp = np.abs(
        librosa.stft(player.signal[:, 0], n_fft=n_fft, hop_length=80, win_length=400, window="hann", center=True)
    )
    sp = librosa.amplitude_to_db(sp / sp.max()).T[:, int(100 * n_fft / sr) : int(4000 * n_fft / sr)]
    expected = np.rint((np.clip(sp, -40, 0) + 40) * 255 / 40).astype(int)
    assert spectrum.shape == expected.shape
    assert np.abs(spectrum - expected).max() <= 1


def test_spectrum_rejects_unknown_windows(player):
    from spiny.plugins.spectrum.extractor import SpectrumExtractor

    with pytest.raises(ValueError, match="supported windows"):
        SpectrumExtractor(window="nope").extract()


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
