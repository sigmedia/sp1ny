import numpy as np
import pytest
from pyqtgraph.Qt import QtWidgets


@pytest.fixture
def waveform(qapp):
    import pyqtgraph as pg

    from spiny.core.wav.visualisation import WaveformItem

    plot = pg.PlotWidget()
    plot.resize(400, 200)
    item = WaveformItem(pen="k")
    plot.addItem(item)
    plot.show()
    yield plot, item
    plot.close()


def test_envelope_matches_brute_force(waveform):
    _, item = waveform
    rng = np.random.default_rng(0)
    signal = rng.standard_normal(1_000_003).astype(np.float32)
    item.setSignal(signal, 16000)
    assert [level[0] for level in item._levels] == list(item.PYRAMID_FACTORS)

    for first, last, columns in [(0, signal.size, 400), (123_457, 600_001, 333), (5_000, 9_000, 100)]:
        positions, mins, maxs = item._visibleEnvelope(first, last, columns)
        bounds = list(positions) + [None]
        for i in range(len(positions)):
            # each column covers its pyramid blocks entirely, which may slightly exceed [first, last)
            chunk = signal[bounds[i] : bounds[i + 1] if bounds[i + 1] is not None else last]
            assert mins[i] <= chunk.min() + 1e-6 and maxs[i] >= chunk.max() - 1e-6
        assert mins.min() == pytest.approx(signal[first:last].min(), abs=1e-6) or first > 0
        assert len(positions) <= columns


def test_paints_at_every_zoom_level(waveform):
    plot, item = waveform
    signal = np.sin(np.arange(160_000) / 10).astype(np.float32)
    item.setSignal(signal, 16000)
    assert item.dataBounds(0) == (0.0, 10.0)
    for x_range in [(0, 10), (2, 3), (2, 2.01), (9.999, 10)]:
        plot.setXRange(*x_range, padding=0)
        QtWidgets.QApplication.processEvents()
        assert not plot.grab().isNull()


def test_short_and_empty_signals(waveform):
    plot, item = waveform
    for signal in [np.zeros(0, dtype=np.float32), np.ones(3, dtype=np.float32)]:
        item.setSignal(signal, 16000)
        QtWidgets.QApplication.processEvents()
        plot.grab()


def test_zoomed_out_segments_are_one_pixel_apart(waveform, monkeypatch):
    """One segment per pixel column, evenly spaced: no column is left empty whatever the zoom"""
    import pyqtgraph as pg

    plot, item = waveform
    drawn = []
    real_array_to_path = pg.arrayToQPath
    monkeypatch.setattr(pg, "arrayToQPath", lambda x, y, **kw: drawn.append(x) or real_array_to_path(x, y, **kw))
    item.setSignal(np.zeros(9_600_000, dtype=np.float32), 16000)  # 10 minutes: the case which showed gaps
    for x_range in [(0, 600), (13.7, 211.3)]:
        drawn.clear()
        plot.setXRange(*x_range, padding=0)
        QtWidgets.QApplication.processEvents()
        plot.grab()
        x = drawn[-1][::2]  # one x per segment
        pixel = (x_range[1] - x_range[0]) / item.getViewBox().width()
        assert np.diff(x) == pytest.approx(pixel, rel=0.02)
