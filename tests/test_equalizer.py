import dataclasses

import numpy as np
import pytest
from pyqtgraph.Qt import QtCore, QtGui, QtTest, QtWidgets

from spiny.core.wav.equalizer import DEFAULT_BANDS, Equalizer, EqBand, biquad_coefficients
from spiny.core.wav.equalizer_widget import MAX_FREQUENCY, MAX_GAIN_DB, MIN_FREQUENCY

RATE = 16000


def run(equalizer, signal, block=256):
    """Filter a signal block by block, as the audio callback does"""
    out = signal.astype(np.float32).reshape(-1, 1).copy()
    for start in range(0, out.shape[0], block):
        equalizer.process(out[start : start + block])
    return out[:, 0]


def equalizer_with(*bands, rate=RATE):
    equalizer = Equalizer()
    equalizer.prepare(rate, 1)
    equalizer.setBands(list(bands))
    equalizer._applied = equalizer._spectrum
    return equalizer


def noise(seconds=1.0, rate=RATE):
    return np.random.default_rng(0).normal(0, 0.1, int(seconds * rate))


def sine(frequency, seconds=1.0, rate=RATE):
    return 0.1 * np.sin(2 * np.pi * frequency * np.arange(int(seconds * rate)) / rate)


def rms(x):
    return np.sqrt(np.mean(x**2))


def test_flat_equalizer_leaves_the_signal_untouched():
    equalizer = equalizer_with(*DEFAULT_BANDS)
    signal = noise()
    assert not equalizer.active
    assert np.array_equal(run(equalizer, signal), signal.astype(np.float32))


@pytest.mark.parametrize(
    "band",
    [
        EqBand("peak", 1000.0, 12.0, 1.0),
        EqBand("peak", 1000.0, -18.0, 5.0),
        EqBand("low_shelf", 200.0, 9.0),
        EqBand("high_shelf", 4000.0, -9.0),
    ],
)
def test_matches_the_recursive_filter(band):
    scipy_signal = pytest.importorskip("scipy.signal")
    signal = noise()
    b, a = biquad_coefficients(band, RATE)
    expected = scipy_signal.lfilter(b, a, signal)
    error = run(equalizer_with(band), signal) - expected
    assert 20 * np.log10(rms(error) / rms(expected)) < -60


def test_gain_of_a_peak():
    band = EqBand("peak", 1000.0, 12.0, 1.0)
    signal = sine(1000)
    out = run(equalizer_with(band), signal)[RATE // 2 :]
    assert 20 * np.log10(rms(out) / rms(signal)) == pytest.approx(12.0, abs=0.1)
    far = sine(100)
    out = run(equalizer_with(band), far)[RATE // 2 :]
    assert 20 * np.log10(rms(out) / rms(far)) < 0.3  # a peak only has a small effect a decade away


@pytest.mark.parametrize("block", [64, 1024, 3000])
def test_result_does_not_depend_on_the_size_of_the_blocks(block):
    band = EqBand("peak", 500.0, 6.0, 2.0)
    signal = noise()
    reference = run(equalizer_with(band), signal, 256)
    assert np.allclose(run(equalizer_with(band), signal, block), reference, atol=1e-4)


def test_changing_a_band_during_playback_does_not_click():
    equalizer = equalizer_with(EqBand("peak", 200.0, 0.1))
    signal = sine(200, 0.5)
    half = 4000 + 20  # NOTE: at a peak of the sine: at a zero crossing, even a hard switch would be silent
    first = run(equalizer, signal[:half])
    equalizer.setBands([EqBand("peak", 200.0, 18.0, 1.0)])
    second = run(equalizer, signal[half:])
    out = np.concatenate([first, second])
    # The steepest slope of a sine at the highest level reached; a jump between two filters is far above it
    assert np.abs(np.diff(out)).max() < 1.05 * 2 * np.pi * 200 / RATE * np.abs(out).max()


def test_bypass_and_back():
    equalizer = equalizer_with(EqBand("peak", 1000.0, 12.0, 1.0))
    signal = sine(1000)
    equalizer.setEnabled(False)
    assert not equalizer.active
    run(equalizer, signal[:512])  # the fade towards no filter
    assert np.array_equal(run(equalizer, signal), signal.astype(np.float32))
    equalizer.setEnabled(True)
    assert rms(run(equalizer, signal)[RATE // 2 :]) > 3 * rms(signal)


def test_frequency_above_nyquist_stays_stable():
    equalizer = equalizer_with(EqBand("high_shelf", 20000.0, 12.0), rate=8000)
    assert np.isfinite(run(equalizer, noise(0.5, 8000))).all()


def test_several_channels():
    equalizer = Equalizer()
    equalizer.prepare(RATE, 2)
    equalizer.setBands([EqBand("peak", 1000.0, 12.0, 1.0)])
    out = np.stack([sine(1000), sine(1000)], axis=1).astype(np.float32)
    equalizer.process(out)
    assert np.array_equal(out[:, 0], out[:, 1])


@pytest.fixture
def widget(player):
    from spiny.core.wav.equalizer_widget import ParametricEqWidget

    bands = list(player.equalizer.bands)
    widget = ParametricEqWidget()
    widget.resize(380, 600)
    widget.show()
    QtWidgets.QApplication.processEvents()
    yield widget
    player.equalizer.setBands(bands)
    player.equalizer.setEnabled(True)


def test_panel_has_no_apply_button(widget):
    assert not [button for button in widget.findChildren(QtWidgets.QPushButton) if button.text() == "Apply"]


def test_sliders_change_the_selected_band_at_once(widget, player):
    widget._select(1)
    widget._sGain.setValue(60)
    widget._sQ.setValue(30)
    band = player.equalizer.bands[1]
    assert (band.gain_db, band.q) == (6.0, 3.0)
    assert player.equalizer.active
    assert widget._plot._curve.yData.max() == pytest.approx(6.0, abs=0.2)
    assert widget._plot._nodes[1].pos().y() == 6.0

    widget._cBand.setChecked(False)
    assert not player.equalizer.active


def test_selecting_a_band_changes_nothing(widget, player):
    before = list(player.equalizer.bands)
    for index in range(len(before)):
        widget._select(index)
    assert player.equalizer.bands == before


def test_dragging_a_handle_changes_frequency_and_gain_of_its_band(widget, player):
    widget._plot._nodes[3].setPos(np.log10(2000.0), 30.0)  # above the largest gain
    band = player.equalizer.bands[3]
    assert band.frequency == pytest.approx(2000.0)
    assert band.gain_db == MAX_GAIN_DB
    assert widget._selected == 3
    assert widget._sFrequency.value() == widget._stepOfFrequency(2000.0)


def test_flat_and_enabled(widget, player):
    widget._sGain.setValue(60)
    widget._cEnabled.setChecked(False)
    assert not player.equalizer.active
    assert np.abs(widget._plot._curve.yData).max() == 0
    widget._cEnabled.setChecked(True)
    assert player.equalizer.active
    widget._bFlat.click()
    assert not player.equalizer.active
    assert all(band.gain_db == 0.0 for band in player.equalizer.bands)


def test_every_frequency_slider_step_is_stable(widget):
    for step in (0, widget.FREQUENCY_STEPS):
        assert widget._stepOfFrequency(widget._frequencyOfStep(step)) == step


def position_of(widget, frequency, gain=0.0):
    """The position in the curve widget of a frequency and a gain"""
    plot = widget._plot
    return plot.mapFromScene(plot.getViewBox().mapViewToScene(QtCore.QPointF(np.log10(frequency), gain)))


def double_click(plot, position):
    left = QtCore.Qt.MouseButton.LeftButton
    # NOTE: what a real double click sends: mouseDClick alone has no release, so it would not be a click for pyqtgraph
    QtTest.QTest.mouseClick(plot.viewport(), left, pos=position)
    QtTest.QTest.mouseDClick(plot.viewport(), left, pos=position)
    QtTest.QTest.mouseRelease(plot.viewport(), left, pos=position)
    QtWidgets.QApplication.processEvents()


def test_double_click_on_the_curve_adds_a_band_there(widget, player):
    before = len(player.equalizer.bands)
    double_click(widget._plot, position_of(widget, 2000.0, 6.0))
    bands = player.equalizer.bands
    assert len(bands) == before + 1
    assert bands[-1].kind == "peak"
    assert bands[-1].frequency == pytest.approx(2000.0, rel=0.05)
    assert bands[-1].gain_db == pytest.approx(6.0, abs=0.5)
    assert widget._selected == before
    assert len(widget._plot._nodes) == before + 1 and len(widget._chip_group.buttons()) == before + 1
    assert player.equalizer.active


def test_double_click_on_a_handle_removes_its_band(widget, player):
    bands = list(player.equalizer.bands)
    double_click(widget._plot, position_of(widget, bands[2].frequency))
    assert player.equalizer.bands == bands[:2] + bands[3:]
    assert len(widget._plot._nodes) == len(bands) - 1


def test_right_click_on_a_handle_removes_its_band(widget, player):
    bands = list(player.equalizer.bands)
    position = position_of(widget, bands[1].frequency)
    QtTest.QTest.mouseClick(widget._plot.viewport(), QtCore.Qt.MouseButton.RightButton, pos=position)
    QtWidgets.QApplication.processEvents()
    assert player.equalizer.bands == bands[:1] + bands[2:]


def test_click_on_a_handle_selects_its_band(widget, player):
    bands = list(player.equalizer.bands)
    QtTest.QTest.mouseClick(
        widget._plot.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=position_of(widget, bands[3].frequency)
    )
    QtWidgets.QApplication.processEvents()
    assert widget._selected == 3 and player.equalizer.bands == bands


def test_mouse_drag_moves_a_handle(widget, player):
    bands = list(player.equalizer.bands)
    start = position_of(widget, bands[1].frequency)
    end = position_of(widget, 1000.0, 9.0)
    viewport = widget._plot.viewport()
    left = QtCore.Qt.MouseButton.LeftButton
    QtTest.QTest.mousePress(viewport, left, pos=start)
    for fraction in (0.25, 0.5, 0.75, 1.0):
        position = start + (end - start) * fraction
        event = QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseMove,
            QtCore.QPointF(position),
            QtCore.QPointF(viewport.mapToGlobal(position)),
            QtCore.Qt.MouseButton.NoButton,
            left,
            QtCore.Qt.KeyboardModifier.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(viewport, event)
    QtTest.QTest.mouseRelease(viewport, left, pos=end)
    QtWidgets.QApplication.processEvents()
    band = player.equalizer.bands[1]
    assert band.frequency == pytest.approx(1000.0, rel=0.1)
    assert band.gain_db == pytest.approx(9.0, abs=1.0)
    assert widget._selected == 1


def test_wheel_on_a_handle_changes_its_q(widget, player):
    band = player.equalizer.bands[1]
    position = QtCore.QPointF(position_of(widget, band.frequency))
    event = QtGui.QWheelEvent(
        position,
        QtCore.QPointF(widget._plot.viewport().mapToGlobal(position)),
        QtCore.QPoint(0, 0),
        QtCore.QPoint(0, 120),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QtWidgets.QApplication.sendEvent(widget._plot.viewport(), event)
    QtWidgets.QApplication.processEvents()
    assert player.equalizer.bands[1].q > band.q and widget._selected == 1


def test_buttons_add_and_remove_bands_down_to_none(widget, player):
    count = len(player.equalizer.bands)
    widget._bAdd.click()
    assert len(player.equalizer.bands) == count + 1
    assert player.equalizer.bands[-1].gain_db == 0.0
    assert all(MIN_FREQUENCY <= band.frequency <= MAX_FREQUENCY for band in player.equalizer.bands)

    for _ in range(count + 1):
        widget._bRemove.click()
    assert player.equalizer.bands == []
    assert widget._selected is None
    assert not widget._bRemove.isEnabled() and not widget._band_controls.isEnabled()
    assert not player.equalizer.active

    widget._bAdd.click()  # from nothing
    assert len(player.equalizer.bands) == 1 and widget._selected == 0
    assert widget._band_controls.isEnabled()


def test_kind_of_a_band_can_change(widget, player):
    widget._select(1)
    widget._boxKind.setCurrentIndex(widget._boxKind.findData("high_shelf"))
    assert player.equalizer.bands[1].kind == "high_shelf"


def test_panel_follows_the_theme(widget):
    from spiny.gui.theme import apply_theme, color

    try:
        apply_theme("dark")
        assert widget._plot.backgroundBrush().color() == color("eq_background")
        assert widget._plot._curve.opts["pen"].color() == color("eq_curve")
        assert widget._plot.getAxis("bottom").textPen().color() == color("eq_text")
    finally:
        apply_theme("light")


def test_equalizer_is_heard_during_playback(player, monkeypatch):
    import sounddevice as sd

    streams = []

    class ManualStream:
        def __init__(self, callback, finished_callback, **kwargs):
            self.callback, self.finished = callback, finished_callback
            streams.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(sd, "OutputStream", ManualStream)
    monkeypatch.setattr(sd, "check_output_settings", lambda **k: None)
    player.setWavData(np.ones(RATE, dtype=np.float32) * 0.5)
    bands = list(player.equalizer.bands)
    player.play()
    QtTest.QTest.qWait(50)
    out = np.zeros((1024, 1), dtype=np.float32)
    try:
        streams[0].callback(out, 1024, None, None)
        assert out.max() == pytest.approx(0.5)
        player.equalizer.setBands([dataclasses.replace(bands[0], gain_db=18.0)])
        for _ in range(3):
            streams[0].callback(out, 1024, None, None)
        assert out.max() == 1.0  # boosted, and clipped at full scale
    finally:
        player.equalizer.setBands(bands)
        player.stop()
        streams[0].finished()
