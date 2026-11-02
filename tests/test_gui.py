import gc
import sys

import pytest
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from conftest import EXAMPLES


def test_extended_combobox_completer(qapp):
    from spiny.gui.helpers.widgets import ExtendedComboBox

    box = ExtendedComboBox()
    box.addItems(["a", "b"])
    emitted = []
    box.textActivated.connect(emitted.append)
    box.on_completer_activated("b")
    assert box.currentText() == "b" and emitted == ["b"]


def test_colormaps_are_available_without_matplotlib(qapp):
    from spiny.gui.colormaps import COLORMAP_NAMES, colormap_ticks

    for name in COLORMAP_NAMES:
        ticks = colormap_ticks(name)
        assert len(ticks) == 10 and ticks[0][0] == 0.0 and ticks[-1][0] == 1.0
        assert all(len(color) == 4 and all(0 <= c <= 255 for c in color) for _, color in ticks)


def test_colormaps_match_matplotlib(qapp):
    mpl = pytest.importorskip("matplotlib")
    import numpy as np

    from spiny.gui.colormaps import COLORMAP_NAMES, get_colormap

    positions = np.linspace(0, 1, 33)
    for name in COLORMAP_NAMES:
        expected = mpl.colormaps[name](positions)[:, :3] * 255
        obtained = get_colormap(name).map(positions, mode="float")[:, :3] * 255
        # pyqtgraph stores its maps on 8 bits, and ships the original cividis (matplotlib uses a revised table)
        tolerance = 25 if name == "cividis" else 5
        assert np.abs(obtained - expected).max() < tolerance, name


def test_unknown_colormap(qapp):
    from spiny.gui.colormaps import get_colormap

    with pytest.raises(ValueError):
        get_colormap("jet")


@pytest.fixture(scope="module")
def window(qapp):
    # NOTE: one window for the module: the window takes ownership of the (singleton) control layouts
    from spiny.core import player
    from spiny.raw_data import controller as raw_controller
    from spiny.ui import GUIVisu, discover_plugins, install_exception_hook

    player.loadNewWav(str(EXAMPLES / "arctic_as.wav"))
    raw_controller.loadCoefficientFile(str(EXAMPLES / "arctic_as.neur"), -50, 6.4)
    discover_plugins()
    previous_hook = sys.excepthook
    win = GUIVisu()
    install_exception_hook(win)
    win.show()

    # Modal dialogs would block a headless run: record them instead, the tests check there is none
    dialogs = []
    with pytest.MonkeyPatch.context() as patch:
        for name in ("warning", "critical", "information"):
            patch.setattr(QtWidgets.QMessageBox, name, lambda *a, **k: dialogs.append(a))
        patch.setattr(QtWidgets.QMessageBox, "question", lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Discard)
        win.dialogs = dialogs
        yield win

        # Destroy the window now (not at an arbitrary later garbage collection) so that the next tests
        # get fresh controllers instead of controllers whose widgets disappear under their feet
        win.close()
    sys.excepthook = previous_hook
    win.deleteLater()
    del win
    gc.collect()
    QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_every_plugin_renders_with_time_on_x(window):
    plugins = [window._plugin_list.itemText(i) for i in range(window._plugin_list.count())]
    assert {"Raw DATA", "Spectrogram"} <= set(plugins)
    for name in plugins + plugins:  # selecting a plugin twice must work too
        window._plugin_list.setCurrentText(name)
        QtWidgets.QApplication.processEvents()
        widget = window._visualisation_area._dock_coef._data_plot
        image = widget._imageItem
        x_max = widget._plotItem.getViewBox().state["limits"]["xLimits"][1]
        assert image.mapRectToParent(image.boundingRect()).width() == pytest.approx(x_max, rel=0.05), name
    window._cmap_list.setCurrentText("magma")
    assert window.dialogs == []


def test_waveform_plot_methods_act_on_the_displayed_plot(player):
    from spiny.core.wav.visualisation import WavPlotWidget

    plot = WavPlotWidget()
    plot.setXRange(1, 2, padding=0)
    assert plot.plotItem.getViewBox().viewRange()[0] == pytest.approx([1, 2])


def test_data_widget_renders_only_the_visible_slice(qapp):
    import numpy as np
    from pyqtgraph.Qt import QtGui

    from spiny.gui.widgets import DataWidget

    widget = DataWidget()
    widget.resize(800, 300)
    widget.show()
    data = np.arange(100_000 * 20, dtype=np.float32).reshape(100_000, 20)
    widget.setLimits(xMin=0, xMax=1000)
    widget.setImageData(data, transform=QtGui.QTransform.fromScale(0.01, 1.0))  # 10 ms frames
    widget.setXRange(500, 510, padding=0)  # 10 s visible = 1000 frames
    QtWidgets.QApplication.processEvents()
    widget.grab()

    image = widget._imageItem
    assert image.image.base is not None  # a view on the data, not a copy
    assert image.image.shape[0] <= 2000 + 2
    rect = image.mapRectToParent(image.boundingRect())
    assert rect.left() <= 500 and rect.right() >= 510  # the slice covers the visible range, at the right place
    assert image.qimage.width() <= image.image.shape[0]

    widget.setXRange(0, 1000, padding=0)  # zoom out: the slice grows to the whole data
    QtWidgets.QApplication.processEvents()
    widget.grab()
    assert image.image.shape[0] == data.shape[0] and image.qimage.width() < 2000
    widget.close()


def test_switching_plugin_releases_the_previous_data(window):
    from spiny.core import plugin_entry_dict

    window._plugin_list.setCurrentText("Spectrogram")
    QtWidgets.QApplication.processEvents()
    spectrum = plugin_entry_dict["Spectrogram"]
    assert spectrum.widget._imageItem.image is not None and spectrum._extractor.spectrogram is not None

    window._plugin_list.setCurrentText("Raw DATA")
    QtWidgets.QApplication.processEvents()
    assert spectrum.widget._imageItem.image is None and spectrum._extractor.spectrogram is None
    assert plugin_entry_dict["Raw DATA"].widget._imageItem.image is not None


def test_open_wav_refreshes_the_views(window):
    from spiny.core import player

    window.loadWav(str(EXAMPLES / "arctic_a0002.wav"))
    x_max = window._visualisation_area._dock_wav.wav_plot.plotItem.vb.state["limits"]["xLimits"][1]
    assert x_max == pytest.approx(player.duration) == pytest.approx(3.755)
    assert window._filename_label.text().endswith("arctic_a0002.wav")


def test_unhandled_exceptions_are_shown(window):
    window.dialogs.clear()
    sys.excepthook(ValueError, ValueError("boom"), None)
    assert len(window.dialogs) == 1


def test_data_widget_does_not_import_matplotlib(qapp):
    import subprocess

    code = (
        "import sys; from pyqtgraph.Qt import QtWidgets; app = QtWidgets.QApplication([]); "
        "from spiny.gui.widgets import DataWidget; DataWidget(); "
        "assert 'matplotlib' not in sys.modules; import importlib.util; "
        "assert importlib.util.find_spec('matplotlib') is None or __import__('matplotlib')"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_set_matrix_places_the_data_in_seconds_and_y_range(qapp):
    import numpy as np

    from spiny.gui.widgets import DataWidget

    widget = DataWidget()
    widget.resize(600, 300)
    widget.show()
    widget.setMatrix(np.zeros((200, 50), dtype=np.uint8), 0.01, (100.0, 4100.0), levels=(0, 255))
    QtWidgets.QApplication.processEvents()

    limits = widget._plotItem.getViewBox().state["limits"]
    assert limits["xLimits"] == [0, 2.0] and limits["yLimits"] == [100.0, 4100.0]
    image = widget._imageItem
    rect = image.mapRectToParent(image.boundingRect())
    assert rect.left() == pytest.approx(0) and rect.right() == pytest.approx(2.0)
    assert rect.top() == pytest.approx(100.0) and rect.bottom() == pytest.approx(4100.0)
    widget.close()


def test_click_on_a_plot_moves_the_cursor(window):
    from spiny.core import player

    class Click:
        def __init__(self, position, button=QtCore.Qt.MouseButton.LeftButton):
            self._position, self._button = position, button

        def button(self):
            return self._button

        def pos(self):
            return self._position

        def accept(self):
            pass

    wav_plot = window._visualisation_area._dock_wav.wav_plot
    wav_plot.setXRange(0, 1, padding=0)
    view = wav_plot.getViewBox()
    view.mouseClickEvent(Click(view.mapFromView(QtCore.QPointF(0.5, 0))))
    assert abs(player.position - 0.5) < 0.01
    player.seek(0.0)


def test_transport_and_output_are_separate_movable_toolbars(window):
    toolbars = {toolbar.windowTitle(): toolbar for toolbar in window.findChildren(QtWidgets.QToolBar)}
    assert set(toolbars) == {"Transport", "Output", "View"}
    assert all(toolbar.isMovable() for toolbar in toolbars.values())
    window.addToolBar(QtCore.Qt.ToolBarArea.BottomToolBarArea, toolbars["Output"])
    assert window.toolBarArea(toolbars["Output"]) == QtCore.Qt.ToolBarArea.BottomToolBarArea


def test_repeated_views_do_not_leak_widgets(window):
    """Opening a file many times used to crash: a new Qt object could be returned as a stale layout item wrapper"""
    from spiny.annotations import get_controller
    from spiny.core import player
    from spiny.gui.items import PlayheadLine

    annotations = get_controller()
    annotations._model.annotations["tier"] = []

    def live_objects(kind):
        QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        gc.collect()
        return sum(isinstance(obj, kind) for obj in gc.get_objects())

    for _ in range(3):
        window.loadWav(str(player.filename))
    nb_lines = live_objects(PlayheadLine)
    nb_layout_items = live_objects(QtWidgets.QWidgetItem)

    for _ in range(10):
        window.loadWav(str(player.filename))
    assert live_objects(PlayheadLine) == nb_lines
    assert live_objects(QtWidgets.QWidgetItem) == nb_layout_items
    assert window._visualisation_area._dock_annotation.vbox.count() == len(annotations._model.annotations)


def test_reloading_clears_the_selected_annotation(window):
    from spiny.annotations import get_controller
    from spiny.annotations.model import Annotation

    annotations = get_controller()
    annotations._model.annotations["tier"] = [Annotation(0.1, 0.2, "a")]
    annotations.resetView()
    window._visualisation_area._dock_wav.wav_plot.setXRange(0, 0.3, padding=0)
    item = window._visualisation_area._dock_annotation.tiers_dict["tier"].annotation_items[0]
    annotations.update_current_annotation(item)
    annotations.resetView()
    assert annotations._current_annotation is None


def test_waveform_path_is_only_built_when_the_view_changes(player, monkeypatch):
    from spiny.core.wav.visualisation import WaveformItem

    item = WaveformItem()
    item.setSignal(player.signal[:, 0], player.sampling_rate)
    builds = []
    build = item._buildPath
    monkeypatch.setattr(item, "_buildPath", lambda *args: builds.append(args) or build(*args))

    class View:
        range = (0.0, 1.0)

        def viewRange(self):
            return (self.range, (-1, 1))

        def width(self):
            return 100

    view = View()
    monkeypatch.setattr(item, "getViewBox", lambda: view)
    image = QtGui.QImage(100, 100, QtGui.QImage.Format.Format_RGB32)
    painter = QtGui.QPainter(image)
    item.paint(painter)
    item.paint(painter)
    assert len(builds) == 1
    view.range = (0.0, 0.5)
    item.paint(painter)
    assert len(builds) == 2
    painter.end()


def test_playhead_only_moves_when_visible_on_screen(window):
    from spiny.core import player
    from spiny.gui.items import PlayheadLine

    wav_plot = window._visualisation_area._dock_wav.wav_plot
    line = next(item for item in wav_plot.getPlotItem().items if isinstance(item, PlayheadLine))
    wav_plot.setXRange(0, 1, padding=0)
    player.seek(0.5)
    line._follow()
    assert line.value() == 0.5

    pixel = 1 / wav_plot.getViewBox().width()
    player.seek(0.5 + pixel / 10)
    line._follow()
    assert line.value() == 0.5
    player.seek(0.5 + 2 * pixel)
    line._follow()
    assert line.value() == player.position
    player.seek(0.0)


def test_every_theme_defines_the_same_colours_and_they_are_valid():
    from pyqtgraph.Qt import QtGui
    from spiny.gui.theme import THEMES

    names = {frozenset(colors) for colors in THEMES.values()}
    assert len(names) == 1
    assert all(QtGui.QColor(value).isValid() for colors in THEMES.values() for value in colors.values())


def test_switching_the_theme_updates_what_is_on_the_screen(window):
    from spiny.gui.items import PlayheadLine
    from spiny.gui.theme import apply_theme, color, current_theme, toggle_theme

    wav_plot = window._visualisation_area._dock_wav.wav_plot
    apply_theme("light")
    try:
        toggle_theme()
        assert current_theme() == "dark"
        assert QtWidgets.QApplication.instance().palette().color(QtGui.QPalette.ColorRole.Window) == color("window")
        assert wav_plot.backgroundBrush().color() == color("plot_background")
        assert wav_plot._waveform._pen.color() == color("waveform")
        assert wav_plot.getAxis("bottom").pen().color() == color("plot_foreground")
        line = next(item for item in wav_plot.getPlotItem().items if isinstance(item, PlayheadLine))
        assert line.pen.color() == color("playhead")
        window.grab()
    finally:
        apply_theme("light")


def view_widget(window):
    from spiny.core.wav import ViewWidget

    return window.findChild(ViewWidget)


def visible_range(window):
    return window._visualisation_area._dock_wav.wav_plot.getViewBox().viewRange()[0]


def test_zoom_buttons(window):
    from spiny.core import player

    view = view_widget(window)
    view.zoomFit()
    player.seek(player.duration / 2)
    before = visible_range(window)
    view._bZoomIn.click()
    x_min, x_max = visible_range(window)
    assert x_max - x_min == pytest.approx((before[1] - before[0]) / 2, rel=0.01)
    assert (x_min + x_max) / 2 == pytest.approx(player.duration / 2, rel=0.01)

    # Zooming out near the end stays in the signal
    player.seek(player.duration)
    view._bZoomOut.click()
    x_min, x_max = visible_range(window)
    assert x_max <= player.duration * 1.001

    view._bZoomFit.click()
    assert visible_range(window)[1] - visible_range(window)[0] == pytest.approx(player.duration, rel=0.01)
    player.seek(0.0)


def test_view_follows_the_playhead(window, monkeypatch):
    from spiny.core import player

    view = view_widget(window)
    wav_plot = window._visualisation_area._dock_wav.wav_plot
    wav_plot.setXRange(0, 0.2, padding=0)
    monkeypatch.setattr(type(player), "is_playing", property(lambda self: True))
    monkeypatch.setattr(type(player), "position", property(lambda self: 0.5))

    view._bFollow.setChecked(False)
    view.followPlayhead()
    assert visible_range(window)[0] == pytest.approx(0, abs=0.01)

    view._bFollow.setChecked(True)
    view.followPlayhead()
    assert visible_range(window)[0] == pytest.approx(0.5, abs=0.01)
    assert visible_range(window)[1] - visible_range(window)[0] == pytest.approx(0.2, abs=0.01)


def test_theme_button_switches_the_theme(window):
    from spiny.gui.theme import apply_theme, current_theme

    apply_theme("light")
    try:
        view_widget(window)._bTheme.click()
        assert current_theme() == "dark"
    finally:
        apply_theme("light")


def press(widget, key):
    from pyqtgraph.Qt import QtTest

    QtTest.QTest.keyClick(widget, key)
    QtWidgets.QApplication.processEvents()


def test_shortcuts_reach_the_buttons_but_not_while_typing(window):
    from spiny.core import player

    from pyqtgraph.Qt import QtTest

    window.activateWindow()
    assert QtTest.QTest.qWaitForWindowActive(window, 2000)

    before = player.loop_activated
    press(window, QtCore.Qt.Key.Key_L)
    assert player.loop_activated != before
    press(window, QtCore.Qt.Key.Key_L)
    assert player.loop_activated == before

    player.seek(0.0)
    press(window, QtCore.Qt.Key.Key_Right)
    assert player.position > 0
    press(window, QtCore.Qt.Key.Key_Home)
    assert player.position == 0

    field = QtWidgets.QLineEdit(window)
    field.show()
    field.setFocus()
    QtWidgets.QApplication.processEvents()
    press(field, QtCore.Qt.Key.Key_L)
    press(field, QtCore.Qt.Key.Key_Space)
    field.deleteLater()
    assert field.text() == "l "
    assert player.loop_activated == before and not player.is_playing


def answer_unsaved_question(monkeypatch, button):
    asked = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", lambda *a, **k: asked.append(a) or button)
    return asked


def test_closing_asks_about_unsaved_annotations(window, monkeypatch, tmp_path):
    from spiny.annotations import get_controller
    from spiny.annotations.model import Annotation, AnnotationSet

    Button = QtWidgets.QMessageBox.StandardButton
    controller = get_controller()
    controller.setAnnotationModel(AnnotationSet({"t": [Annotation(0.1, 0.2, "a")]}, set()))

    def closes():
        event = QtGui.QCloseEvent()
        window.closeEvent(event)
        return event.isAccepted()

    asked = answer_unsaved_question(monkeypatch, Button.Cancel)
    assert closes() and not asked  # nothing changed: no question

    for change in (
        lambda: setattr(controller.model.annotations["t"][0], "label", "b"),
        lambda: setattr(controller.model.annotations["t"][0], "end_time", 0.3),
        lambda: controller.model.ignored.add("t"),
    ):
        controller.setAnnotationModel(AnnotationSet({"t": [Annotation(0.1, 0.2, "a")]}, set()))
        change()
        assert not closes()

    # Save, but the file dialog is cancelled: the window stays open
    answer_unsaved_question(monkeypatch, Button.Save)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    assert not closes()

    # Save for real: nothing to ask anymore
    target = tmp_path / "saved.json"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    assert closes() and target.exists()
    asked = answer_unsaved_question(monkeypatch, Button.Cancel)
    assert closes() and not asked

    # Discard: closes without saving
    controller.model.annotations["t"][0].label = "c"
    answer_unsaved_question(monkeypatch, Button.Discard)
    assert closes()
    controller.setAnnotationModel(AnnotationSet({}, set()))


def test_loading_a_file_asks_about_unsaved_annotations(window, monkeypatch, tmp_path):
    from spiny.annotations import get_controller
    from spiny.annotations.model import Annotation, AnnotationSet

    controller = get_controller()
    model = AnnotationSet({"t": [Annotation(0.1, 0.2, "a")]}, set())
    controller.setAnnotationModel(model)
    model.annotations["t"][0].label = "edited"
    answer_unsaved_question(monkeypatch, QtWidgets.QMessageBox.StandardButton.Cancel)
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: pytest.fail("must not ask for a file")
    )
    controller._load_annotation_file()
    assert controller.model is model
    controller.setAnnotationModel(AnnotationSet({}, set()))
