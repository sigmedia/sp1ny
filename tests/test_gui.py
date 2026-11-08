import gc
import sys
import time

import numpy as np
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
    assert set(toolbars) == {"Transport", "Output", "View", "Annotations"}
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


def process_events():
    for _ in range(5):
        QtWidgets.QApplication.processEvents()


def test_ratio_between_plots_and_controls_follows_the_user_and_survives_resizing(window):
    splitter = window._main_splitter
    window.resize(1600, 900)
    process_events()
    assert splitter.sizes()[0] == pytest.approx(3 * splitter.sizes()[1], rel=0.02)

    splitter.setSizes([800, 800])  # the same as dragging the handle
    process_events()
    for size in ((1000, 700), (1800, 1000), (1600, 900)):
        window.resize(*size)
        process_events()
        assert splitter.sizes()[0] == pytest.approx(splitter.sizes()[1], rel=0.03)
    splitter.setSizes([1200, 400])


def test_vertical_ratio_of_the_plots_survives_resizing(window):
    area = window._visualisation_area

    def fractions():
        heights = [dock.height() for dock in (area._dock_coef, area._dock_annotation, area._dock_wav)]
        return [height / sum(heights) for height in heights]

    window.resize(1600, 900)
    process_events()
    before = fractions()
    window.resize(1600, 1100)
    process_events()
    assert fractions() == pytest.approx(before, abs=0.01)


def test_window_can_get_small_and_the_toolbars_wrap(window):
    from spiny.ui import GUIVisu

    toolbars = window.findChildren(QtWidgets.QToolBar)
    window.resize(1600, 900)
    process_events()
    assert not any(window.toolBarBreak(toolbar) for toolbar in toolbars)

    window.resize(GUIVisu.MINIMUM_SIZE)
    process_events()
    assert window.size() == GUIVisu.MINIMUM_SIZE
    assert any(window.toolBarBreak(toolbar) for toolbar in toolbars)
    assert all(toolbar.width() >= toolbar.sizeHint().width() for toolbar in toolbars)  # nothing is cut

    window.resize(1600, 900)
    process_events()
    assert not any(window.toolBarBreak(toolbar) for toolbar in toolbars)


def test_control_groups_are_at_the_top_with_the_height_they_need(window):
    window.resize(1600, 1200)
    previous_plugin = window._plugin_list.currentText()
    window._plugin_list.setCurrentText("Spectrogram")
    process_events()
    general = window._plugin_list.parentWidget()
    assert general.height() <= general.sizeHint().height() + 2
    assert general.y() < 30
    panel = window._plugin_panel
    assert panel.y() == pytest.approx(general.geometry().bottom(), abs=30)
    assert panel.height() <= panel.sizeHint().height() + 2
    window._plugin_list.setCurrentText(previous_plugin)


def test_groups_of_the_other_tabs_have_the_height_they_need(window):
    tabs = window.findChild(QtWidgets.QTabWidget)
    window.resize(1600, 1200)
    for index, boxes in ((1, ("_file_box", "_tier_box", "_ipa_box")), (2, ("_file_box", "_eq_widget"))):
        tabs.setCurrentIndex(index)
        process_events()
        layout = window._annotation_layout if index == 1 else window._audio_layout
        for name in boxes:
            box = getattr(layout, name)
            assert box.height() <= box.sizeHint().height() + 2, name
    tabs.setCurrentIndex(0)


def test_tier_list_shows_at_least_four_rows_and_scrolls_above_six(qapp):
    from spiny.annotations.control import QListWidgetItemHideable, TierList

    def height_of(nb_rows, tiers):
        return nb_rows * tiers.sizeHintForRow(0) + 2 * tiers.frameWidth()

    tiers = TierList()
    assert tiers.MIN_VISIBLE_ROWS == 4
    for name in "ab":
        QListWidgetItemHideable(tiers).setText(name)
    assert tiers.height() == height_of(4, tiers)
    for name in "cde":
        QListWidgetItemHideable(tiers).setText(name)
    assert tiers.height() == height_of(5, tiers)
    for name in "fghij":
        QListWidgetItemHideable(tiers).setText(name)
    assert tiers.height() == height_of(tiers.MAX_VISIBLE_ROWS, tiers)


@pytest.mark.parametrize(
    "seconds, spacing, text",
    [
        (0, 1, "0 s"),
        (12.5, 0.5, "12.5 s"),
        (45, 15, "45 s"),
        (60, 30, "1:00 min"),
        (150, 30, "2:30 min"),
        (61.25, 0.05, "1:01.25 min"),
        (600, 60, "10:00 min"),
        (3600, 600, "1:00:00 h"),
        (3750, 30, "1:02:30 h"),
        (36000, 3600, "10:00:00 h"),
    ],
)
def test_time_ticks_use_seconds_minutes_and_hours(seconds, spacing, text):
    from spiny.core.wav.visualisation import format_axis_time

    assert format_axis_time(seconds, spacing) == text


def test_time_axis_never_uses_kiloseconds(window):
    axis = window._visualisation_area._dock_wav.wav_plot.getAxis("bottom")
    assert axis.tickSpacing(0, 600, 1000)[0][0] == 60
    assert axis.tickSpacing(0, 7200, 1000)[0][0] == 900
    assert axis.tickSpacing(0, 1, 1000)[0][0] < 1
    assert not axis.autoSIPrefix and "x0" not in axis.labelString()


@pytest.fixture
def overlays(window):
    """The overlays and the window on the spectrogram, with nothing enabled at the start and at the end"""
    from spiny.core.overlay import overlay_entry_dict

    previous = window._plugin_list.currentText()
    window._plugin_list.setCurrentText("Spectrogram")
    process_events()
    yield overlay_entry_dict
    for overlay in overlay_entry_dict.values():
        overlay.setEnabled(False)
    window._plugin_list.setCurrentText(previous)


def tick(window, name, checked=True):
    panel = window._overlay_panel
    item = panel._list.findItems(name, QtCore.Qt.MatchFlag.MatchExactly)[0]
    item.setCheckState(QtCore.Qt.CheckState.Checked if checked else QtCore.Qt.CheckState.Unchecked)


def wait_for_analysis(overlay, condition=None):
    deadline = time.time() + 10
    while time.time() < deadline:
        QtWidgets.QApplication.processEvents()
        if not overlay._running and not overlay._draw_timer.isActive() and (condition is None or condition()):
            return
        time.sleep(0.002)
    pytest.fail("the analysis of the overlay did not end")


def test_overlays_are_listed_according_to_the_visualisation(window, overlays):
    panel = window._overlay_panel
    names = {panel._list.item(row).text() for row in range(panel._list.count())}
    assert {"Formants", "F0", "Mask"} == names
    assert not panel._none.isVisibleTo(panel)

    window._plugin_list.setCurrentText("Raw DATA")  # it does not support overlays
    assert panel._list.count() == 0
    assert panel._none.isVisibleTo(panel)
    assert overlays["Formants"]._plot is None


def test_several_overlays_can_be_shown_and_they_are_drawn_on_the_plot(window, overlays):
    window._visualisation_area._dock_wav.wav_plot.setXRange(0, 3, padding=0)
    tick(window, "Formants")
    tick(window, "F0")
    formants, f0 = overlays["Formants"], overlays["F0"]
    wait_for_analysis(formants, lambda: formants._chunks)
    wait_for_analysis(f0, lambda: f0._chunks)

    plot = window._current_controller.widget
    assert formants._curves["F1"] in plot._plotItem.items and f0._curves["F0"] in plot._plotItem.items
    assert formants._curves["F1"].isVisible() and f0._curves["F0"].isVisible()
    assert not formants._curves["F5"].isVisible()  # not shown by default
    assert np.isfinite(formants._curves["F1"].yData).any() and np.isfinite(f0._curves["F0"].yData).any()

    tick(window, "F0", False)
    assert formants.enabled and not f0.enabled and not f0._curves["F0"].isVisible()


def test_panel_shows_the_configuration_of_the_highlighted_overlay(window, overlays):
    panel = window._overlay_panel
    for row in range(panel._list.count()):
        panel._list.setCurrentRow(row)
        name = panel._list.item(row).text()
        assert [n for n, p in panel._panels.items() if p.isVisibleTo(panel)] == [name]
        assert not panel._list.item(row).checkState() == QtCore.Qt.CheckState.Checked  # highlighting is not showing


def test_overlay_is_not_drawn_nor_computed_when_nothing_is_plotted(window, overlays):
    controller = window._current_controller
    wav_plot = window._visualisation_area._dock_wav.wav_plot
    overlay = overlays["Formants"]
    controller.max_duration = 1
    try:
        wav_plot.setXRange(0, 3, padding=0)
        controller._scheduleAnalysis()
        deadline = time.time() + 10
        while controller.widget.isPlotting() and time.time() < deadline:
            QtWidgets.QApplication.processEvents()
        assert not controller.widget.isPlotting()

        tick(window, "Formants")
        process_events()
        assert not overlay.is_active and not overlay._running
        assert not overlay._curves["F1"].isVisible()

        wav_plot.setXRange(0, 0.5, padding=0)  # zooming in: the spectrogram is back, and the overlay too
        deadline = time.time() + 10
        while not controller.widget.isPlotting() and time.time() < deadline:
            QtWidgets.QApplication.processEvents()
        wait_for_analysis(overlay, lambda: overlay._chunks)
        assert overlay.is_active and overlay._curves["F1"].isVisible()
    finally:
        controller.max_duration = 30


def test_changing_the_settings_computes_again_and_the_look_does_not(window, overlays):
    import dataclasses

    window._visualisation_area._dock_wav.wav_plot.setXRange(0, 3, padding=0)
    overlay = overlays["Formants"]
    tick(window, "Formants")
    wait_for_analysis(overlay, lambda: overlay._chunks)
    chunks = overlay._chunks

    overlay.setColor("F1", QtGui.QColor("#123456"))
    assert overlay._curves["F1"].opts["pen"].color() == QtGui.QColor("#123456")
    del overlay._colors["F1"]
    overlay.setLineWidth(4)
    assert overlay._curves["F1"].opts["pen"].widthF() == 4
    overlay.setLineWidth(2)
    assert overlay._chunks is chunks

    settings = overlay.settings
    overlay.setSettings(dataclasses.replace(settings, max_frequency=4500.0))
    assert overlay._chunks is not chunks
    wait_for_analysis(overlay, lambda: overlay._chunks)
    overlay.setSettings(settings)


def test_a_new_file_forgets_the_tracks(window, overlays):
    from spiny.core import player

    window._visualisation_area._dock_wav.wav_plot.setXRange(0, 3, padding=0)
    overlay = overlays["F0"]
    tick(window, "F0")
    wait_for_analysis(overlay, lambda: overlay._chunks)
    before = overlay._chunks
    window.loadWav(str(player.filename))
    assert overlay._chunks is not before


def test_failed_analysis_is_reported_once(window, overlays, monkeypatch, caplog):
    window._visualisation_area._dock_wav.wav_plot.setXRange(0, 3, padding=0)
    overlay = overlays["F0"]
    overlay._forgetChunks()
    calls = []

    def fail(*args):
        calls.append(args)
        raise ValueError("no way")

    monkeypatch.setattr(overlay, "compute", fail)
    tick(window, "F0")
    wait_for_analysis(overlay, lambda: overlay._chunks)
    nb_calls = len(calls)
    assert "failed" in caplog.text and nb_calls >= 1
    window._visualisation_area._dock_wav.wav_plot.setXRange(0, 2, padding=0)
    wait_for_analysis(overlay)
    assert len(calls) == nb_calls
    monkeypatch.undo()
    overlay._forgetChunks()


def test_line_breaks_at_gaps_and_jumps():
    from spiny.core.overlay import connected_points

    values = np.array([100, 101, np.nan, 200, 202, 900, 905], dtype=np.float32)
    assert connected_points(values).tolist() == [1, 0, 0, 1, 0, 1, 0]


def turn_wheel(plot, x=0, y=0, shift=False):
    """Send what a mouse wheel or two fingers on a trackpad send, over the centre of the plot"""
    view = plot.getViewBox() if hasattr(plot, "getViewBox") else plot._plotItem.getViewBox()
    position = QtCore.QPointF(plot.mapFromScene(view.sceneBoundingRect().center()))
    modifiers = QtCore.Qt.KeyboardModifier.ShiftModifier if shift else QtCore.Qt.KeyboardModifier.NoModifier
    event = QtGui.QWheelEvent(
        position,
        QtCore.QPointF(plot.viewport().mapToGlobal(position)),
        QtCore.QPoint(0, 0),
        QtCore.QPoint(x, y),
        QtCore.Qt.MouseButton.NoButton,
        modifiers,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QtWidgets.QApplication.sendEvent(plot.viewport(), event)
    QtWidgets.QApplication.processEvents()


@pytest.fixture
def plots(window):
    """The three kinds of plot which show the time, on a view with room around"""
    from spiny.annotations import get_controller
    from spiny.annotations.model import Annotation, AnnotationSet

    window._plugin_list.setCurrentText("Spectrogram")
    get_controller().setAnnotationModel(AnnotationSet({"t": [Annotation(0.1, 0.2, "a")]}, set()))
    area = window._visualisation_area
    wav_plot = area._dock_wav.wav_plot
    wav_plot.setXRange(1, 2, padding=0)
    process_events()
    yield {
        "waveform": wav_plot,
        "spectrogram": window._current_controller.widget,
        "tier": area._dock_annotation.tiers_dict["t"],
    }
    get_controller().setAnnotationModel(AnnotationSet({}, set()))
    window._plugin_list.setCurrentText("Raw DATA")


@pytest.mark.parametrize("name", ["waveform", "spectrogram", "tier"])
def test_wheel_up_and_down_zoom_on_every_plot(window, plots, name):
    wav_range = plots["waveform"].getViewBox().viewRange
    before = wav_range()[0]
    turn_wheel(plots[name], y=120)
    x_min, x_max = wav_range()[0]
    assert x_max - x_min < before[1] - before[0]
    assert wav_range()[1] == plots["waveform"].getViewBox().viewRange()[1]

    width = x_max - x_min
    turn_wheel(plots[name], y=-120)
    assert wav_range()[0][1] - wav_range()[0][0] > width


@pytest.mark.parametrize("name", ["waveform", "spectrogram", "tier"])
@pytest.mark.parametrize("gesture", [{"x": 120}, {"y": 120, "shift": True}, {"x": 120, "shift": True}])
def test_two_fingers_sideways_and_shift_wheel_move_on_every_plot(window, plots, name, gesture):
    wav_range = plots["waveform"].getViewBox().viewRange
    x_min, x_max = wav_range()[0]
    turn_wheel(plots[name], **gesture)
    # NOTE: a tier is a little narrower than the waveform (scroll bar): the link between them is not exact to the pixel
    assert wav_range()[0][0] == pytest.approx(x_min - 0.1 * (x_max - x_min), abs=5e-3)
    assert wav_range()[0][1] - wav_range()[0][0] == pytest.approx(x_max - x_min, abs=5e-3)

    opposite = {key: -value if key != "shift" else value for key, value in gesture.items()}
    turn_wheel(plots[name], **opposite)
    assert wav_range()[0][0] == pytest.approx(x_min, abs=5e-3)


def test_wheel_follows_the_configuration(window, plots, monkeypatch):
    from spiny.gui import shortcuts

    monkeypatch.setitem(shortcuts.WHEEL_ACTIONS, "wheel_up_down", "pan")
    monkeypatch.setitem(shortcuts.WHEEL_ACTIONS, "wheel_left_right", "zoom")
    wav_range = plots["waveform"].getViewBox().viewRange
    x_min, x_max = wav_range()[0]
    turn_wheel(plots["waveform"], y=120)
    assert wav_range()[0][1] - wav_range()[0][0] == pytest.approx(x_max - x_min, abs=1e-3)
    assert wav_range()[0][0] < x_min

    width = wav_range()[0][1] - wav_range()[0][0]
    turn_wheel(plots["waveform"], x=120)
    assert wav_range()[0][1] - wav_range()[0][0] < width

    monkeypatch.setitem(shortcuts.WHEEL_ACTIONS, "wheel_up_down", "none")
    before = wav_range()
    turn_wheel(plots["waveform"], y=120)
    assert wav_range() == before


def test_reset_button_of_the_plugin(window, plots):
    from spiny.plugins.spectrum.extractor import SpectrogramSettings

    controller = window._current_controller
    controller._time_step.setValue(12)
    controller._window_length.setValue(50)
    controller._max_level.setValue(-20)
    controller._max_frequency.setValue(3000)
    controller._max_duration.setValue(100)
    window._cmap_list.setCurrentIndex(2)
    process_events()

    button = next(
        b for b in window._plugin_panel.findChildren(QtWidgets.QPushButton) if b.text() == "Reset to defaults"
    )
    button.click()
    process_events()
    assert controller._extractor.settings == SpectrogramSettings()
    assert controller.max_duration == 30
    assert controller._max_level.value() == 0 and controller._time_step.value() == 2
    assert controller._max_frequency.value() == 5000 and controller._max_duration.value() == 30
    assert controller.widget.db_range == (-70.0, 0.0)
    assert window._cmap_list.currentIndex() == 0


def test_every_plugin_has_a_reset_button(window):
    previous = window._plugin_list.currentText()
    window._plugin_list.setCurrentText("Raw DATA")
    assert [b for b in window._plugin_panel.findChildren(QtWidgets.QPushButton) if b.text() == "Reset to defaults"]
    window._plugin_list.setCurrentText(previous)


def test_reset_button_of_the_overlay(window, overlays):
    panel = window._overlay_panel
    panel._list.setCurrentRow([panel._list.item(row).text() for row in range(panel._list.count())].index("Formants"))
    overlay = overlays["Formants"]
    tick(window, "Formants")
    defaults = overlay.settings

    overlay.setSettings(type(defaults)(max_frequency=4000.0))
    overlay.setColor("F1", QtGui.QColor("#123456"))
    overlay.setTrackShown("F1", False)
    overlay.setTrackShown("F5", True)
    overlay.setLineWidth(5)
    old_panel = panel._panels["Formants"]

    panel._bReset.click()
    process_events()
    assert overlay.settings == defaults
    assert overlay.isTrackShown("F1") and not overlay.isTrackShown("F5")
    assert overlay.line_width == overlay.DEFAULT_LINE_WIDTH
    assert overlay.color("F1").name() != "#123456"
    assert overlay.enabled  # still shown
    assert panel._panels["Formants"] is not old_panel and panel._panels["Formants"].isVisibleTo(panel)
    sliders = panel._panels["Formants"].findChildren(QtWidgets.QSlider)
    assert any(slider.value() == 5500 for slider in sliders)


@pytest.fixture
def mask_overlay(window, overlays, tmp_path):
    """The mask overlay with a mask: everything is visible on the left half of the signal, nothing on the right one"""
    from spiny.core import player

    window._visualisation_area._dock_wav.wav_plot.setXRange(0, player.duration, padding=0)
    spectrogram = window._current_controller._extractor
    deadline = time.time() + 10
    while not spectrogram.spectrogram.covers(0, player.duration) and time.time() < deadline:
        QtWidgets.QApplication.processEvents()
    mask = np.ones((1000, 200), dtype=np.float32)
    mask[500:] = 0.0
    filename = tmp_path / "mask.npy"
    np.save(filename, mask)
    overlay = overlays["Mask"]
    overlay.loadMask(filename)
    yield overlay
    overlay.resetConfiguration()
    overlay._file_mask = None


def pixels_of_the_plot(window):
    """Grab the plot of the spectrogram: the colour at 25 % and at 75 % of the time, in the middle of the height"""
    from spiny.core import player

    process_events()
    plot = window._current_controller.widget
    view = plot._plotItem.getViewBox()
    image = plot.grab().toImage()
    y = view.viewRange()[1][1] * 0.5

    def pixel(time_position):
        point = plot.mapFromScene(view.mapViewToScene(QtCore.QPointF(time_position * player.duration, y)))
        return image.pixelColor(point)

    return pixel(0.25), pixel(0.75)


def test_mask_hides_where_the_opacity_is_zero(window, mask_overlay):
    from spiny.gui import theme

    # Without the mask: the plot is not the colour of its background
    left, right = pixels_of_the_plot(window)
    background = theme.color("plot_background")
    assert right != background

    tick(window, "Mask")
    masked_left, masked_right = pixels_of_the_plot(window)
    assert masked_left == left
    assert masked_right == background

    # The colour and the strength
    mask_overlay.setColor("", QtGui.QColor("#ff0000"))
    assert pixels_of_the_plot(window)[1] == QtGui.QColor("#ff0000")
    mask_overlay.setConfiguration(strength=0.0)
    assert pixels_of_the_plot(window)[1] == right
    mask_overlay.setConfiguration(strength=1.0)

    # Inverted: the other side is hidden
    mask_overlay.setConfiguration(invert=True)
    inverted_left, inverted_right = pixels_of_the_plot(window)
    assert inverted_left == QtGui.QColor("#ff0000") and inverted_right == right


def test_mask_layout_in_the_file(window, overlays, tmp_path):
    overlay = overlays["Mask"]
    filename = tmp_path / "wide.npy"
    np.save(filename, np.ones((30, 400), dtype=np.float32))
    overlay.loadMask(filename)
    assert overlay.mask.shape == (30, 400)
    overlay.setConfiguration(swap_axes=True)
    assert overlay.mask.shape == (400, 30)
    overlay.resetConfiguration()
    assert overlay.mask.shape == (30, 400)
    overlay._file_mask = None


def test_mask_is_placed_in_time_and_frequency(window, mask_overlay):
    from spiny.core import player

    tick(window, "Mask")
    process_events()
    rect = mask_overlay._image.mapRectToParent(mask_overlay._image.boundingRect())
    assert rect.left() == pytest.approx(0, abs=1e-6)
    assert rect.right() == pytest.approx(player.duration, rel=0.01)
    assert rect.top() == pytest.approx(0, abs=1e-6)
    assert rect.bottom() == pytest.approx(player.sampling_rate / 2, rel=0.01)

    mask_overlay.setConfiguration(frame_shift=1.0, max_frequency=4000.0)
    rect = mask_overlay._image.mapRectToParent(mask_overlay._image.boundingRect())
    assert rect.right() == pytest.approx(1.0, rel=0.01)  # 1000 frames of 1 ms
    assert rect.bottom() == pytest.approx(4000.0, rel=0.01)


def test_mask_is_not_drawn_when_nothing_is_plotted(window, mask_overlay):
    tick(window, "Mask")
    process_events()
    assert mask_overlay._image.isVisible()
    window._current_controller.widget.clearImageData()
    assert not mask_overlay.is_active and not mask_overlay._image.isVisible()
    window._current_controller.extract()
    process_events()
    assert mask_overlay._image.isVisible()


def test_nothing_is_drawn_without_a_mask(window, overlays):
    overlay = overlays["Mask"]
    tick(window, "Mask")
    process_events()
    assert overlay.mask is None and not overlay._image.isVisible()


def test_panel_loads_a_mask_and_reports_errors(window, overlays, tmp_path, monkeypatch):
    overlay = overlays["Mask"]
    panel = window._overlay_panel
    names = [panel._list.item(row).text() for row in range(panel._list.count())]
    panel._list.setCurrentRow(names.index("Mask"))
    good, bad = tmp_path / "good.npy", tmp_path / "bad.npy"
    np.save(good, np.ones((10, 20)))
    np.save(bad, np.ones((10, 20)) * 3)

    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: (str(good), ""))
    overlay._askFile()
    assert overlay.mask.shape == (10, 20) and "10 frames" in overlay._lFile.text()

    window.dialogs.clear()
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: (str(bad), ""))
    overlay._askFile()
    assert window.dialogs and "between 0 and 1" in window.dialogs[0][2]
    assert str(overlay.filename) == str(good)  # the mask stays
    window.dialogs.clear()

    panel._bReset.click()
    process_events()
    assert overlay.mask is not None  # a reset keeps the mask, only the configuration changes
    overlay._file_mask = None


@pytest.mark.parametrize("index", [0, -1])  # a colormap of pyqtgraph and one defined here
def test_inverted_colormap_is_stable_and_reversed(qapp, index):
    from spiny.gui.colormaps import COLORMAP_NAMES, colormap_ticks

    name = COLORMAP_NAMES[index]
    normal = colormap_ticks(name)
    assert colormap_ticks(name, True) == colormap_ticks(name, True)  # asking twice does not flip it back
    assert colormap_ticks(name) == normal  # and the normal one is not affected
    inverted = colormap_ticks(name, True)
    assert inverted[0][1] == normal[-1][1] and inverted[-1][1] == normal[0][1]


def test_smooth_image_filters_both_axes_and_keeps_the_shape(qapp):
    from spiny.gui.widgets import SMOOTHING_KERNELS, smooth_image

    image = np.zeros((7, 9, 4), dtype=np.uint8)
    image[3, 4] = 240
    box = smooth_image(image, SMOOTHING_KERNELS["Box"])
    assert box.shape == image.shape and box.dtype == np.uint8
    assert box[3, 4, 0] == 240 // 3 // 3 and box[2, 3, 0] == box[3, 4, 0] and box[1, 4, 0] == 0
    gaussian = smooth_image(image, SMOOTHING_KERNELS["Gaussian"])
    assert gaussian[3, 4, 0] > gaussian[2, 4, 0] > gaussian[1, 4, 0] > 0

    flat = np.full((5, 5), 77, dtype=np.uint8)
    assert np.array_equal(smooth_image(flat, SMOOTHING_KERNELS["Gaussian"]), flat)


def test_smoothing_applies_to_every_plugin_and_can_be_reset(window):
    from spiny.gui.widgets import DataWidget

    previous = window._plugin_list.currentText()
    choices = [window._smoothing_list.itemText(i) for i in range(window._smoothing_list.count())]
    assert choices[0] == "None" and {"Bilinear", "Box", "Gaussian"} <= set(choices)

    window._smoothing_list.setCurrentText("Gaussian")
    for name in [window._plugin_list.itemText(i) for i in range(window._plugin_list.count())]:
        window._plugin_list.setCurrentText(name)
        process_events()
        plot = window._current_controller.widget
        if isinstance(plot, DataWidget):
            assert plot._imageItem._smoothing == "Gaussian", name

    window._plugin_list.setCurrentText("Spectrogram")
    process_events()
    window.resetPluginConfiguration()
    process_events()
    assert window._smoothing_list.currentText() == "None"
    assert window._current_controller.widget._imageItem._smoothing == "None"
    window._plugin_list.setCurrentText(previous)


@pytest.mark.parametrize("smoothing", ["Bilinear", "Box", "Gaussian"])
def test_smoothing_changes_what_is_drawn(window, smoothing):
    previous = window._plugin_list.currentText()
    window._plugin_list.setCurrentText("Spectrogram")
    window._visualisation_area._dock_wav.wav_plot.setXRange(0.5, 0.8, padding=0)
    deadline = time.time() + 5
    while time.time() < deadline and window._current_controller._running:
        QtWidgets.QApplication.processEvents()
    process_events()

    def drawn():
        image = window._current_controller.widget.grab().toImage().convertToFormat(QtGui.QImage.Format.Format_RGB32)
        return bytes(image.constBits())

    window._smoothing_list.setCurrentText("None")
    process_events()
    sharp = drawn()
    window._smoothing_list.setCurrentText(smoothing)
    process_events()
    smooth = drawn()
    window._smoothing_list.setCurrentText("None")
    process_events()
    assert smooth != sharp and drawn() == sharp
    window._plugin_list.setCurrentText(previous)


def type_in(slider, text, finish=QtCore.Qt.Key.Key_Return):
    """Type a text in the field of a slider, as a user would"""
    from pyqtgraph.Qt import QtTest

    slider._field.selectAll()
    slider._field.del_()
    QtTest.QTest.keyClicks(slider._field, text)
    QtTest.QTest.keyClick(slider._field, finish)
    QtWidgets.QApplication.processEvents()


@pytest.mark.parametrize(
    "text, value, shown",
    [
        ("42", 42, "42 ms"),
        ("42 ms", 42, "42 ms"),
        ("42,4 ms", 42, "42 ms"),
        ("1000", 100, "100 ms"),  # clipped to the range of the slider
        ("-3", 1, "1 ms"),
        ("a lot", 7, "7 ms"),  # not a number: the value does not change
        ("", 7, "7 ms"),
    ],
)
def test_typing_in_the_field_moves_the_slider(qapp, text, value, shown):
    from spiny.gui.helpers.widgets import LabelledSlider

    slider = LabelledSlider(1, 100, 7, lambda v: f"{v} ms")
    received = []
    slider.valueChanged.connect(received.append)
    type_in(slider, text)
    assert slider.value() == value and slider._field.text() == shown
    assert received == ([] if value == 7 else [value])


def test_value_is_only_applied_at_the_end_of_the_edition(qapp):
    from pyqtgraph.Qt import QtTest
    from spiny.gui.helpers.widgets import LabelledSlider

    slider = LabelledSlider(1, 100, 7)
    received = []
    slider.valueChanged.connect(received.append)
    slider._field.selectAll()
    slider._field.del_()
    QtTest.QTest.keyClicks(slider._field, "42")
    assert received == [] and slider.value() == 7

    slider.show()
    slider._field.setFocus()
    QtWidgets.QApplication.processEvents()
    QtWidgets.QApplication.sendEvent(slider._field, QtGui.QFocusEvent(QtCore.QEvent.Type.FocusOut))
    assert received == [42]


def test_moving_the_slider_updates_the_field(qapp):
    from spiny.gui.helpers.widgets import LabelledSlider

    slider = LabelledSlider(1, 100, 7, lambda v: f"{v} ms")
    slider.setValue(30)
    assert slider._field.text() == "30 ms"


def test_field_of_the_equalizer_frequency_understands_kilohertz(player):
    from spiny.core.wav.equalizer_widget import ParametricEqWidget

    bands = list(player.equalizer.bands)
    widget = ParametricEqWidget()
    try:
        widget._select(1)
        type_in(widget._sFrequency, "2 kHz")
        assert player.equalizer.bands[1].frequency == pytest.approx(2000, rel=0.02)
        type_in(widget._sGain, "-6.5")
        assert player.equalizer.bands[1].gain_db == -6.5
        type_in(widget._sQ, "2.5")
        assert player.equalizer.bands[1].q == 2.5
        assert widget._sGain._field.text() == "-6.5 dB"
        type_in(widget._sFrequency, "0")  # below the range: not a crash
        assert player.equalizer.bands[1].frequency == pytest.approx(widget._frequencyOfStep(0))
    finally:
        player.equalizer.setBands(bands)


def test_field_of_a_spectrogram_setting_starts_the_analysis(window):
    previous = window._plugin_list.currentText()
    window._plugin_list.setCurrentText("Spectrogram")
    process_events()
    controller = window._current_controller
    try:
        type_in(controller._time_step, "7")
        deadline = time.time() + 5
        while controller._extractor.settings.frameshift != 7 and time.time() < deadline:
            QtWidgets.QApplication.processEvents()
        assert controller._extractor.settings.frameshift == 7
        assert controller._time_step._field.text() == "7 ms"
    finally:
        controller._time_step.setValue(2)
        window._plugin_list.setCurrentText(previous)


def test_volume_can_be_typed(window):
    from spiny.core import player
    from spiny.core.wav import OutputWidget

    output = window.findChild(OutputWidget)
    before = player.volume
    try:
        type_in(output._sVolume, "35")
        assert player.volume == 0.35 and output._sVolume._field.text() == "35%"
    finally:
        output._sVolume.setValue(round(before * 100))


def test_voicing_threshold_field_is_on_the_scale_it_shows(window, overlays):
    import dataclasses

    overlay = overlays["F0"]
    default = overlay.settings
    from spiny.gui.helpers.widgets import LabelledSlider

    sliders = window._overlay_panel._panels["F0"].findChildren(LabelledSlider)
    voicing = next(slider for slider in sliders if slider._field.text() == "0.45")
    type_in(voicing, "0.6")
    assert overlay.settings == dataclasses.replace(default, voicing_threshold=0.6)
    overlay.setSettings(default)
    voicing.setValue(45)


@pytest.fixture
def two_locked_tiers(window):
    """Tiers a and b, with boundaries aligned at 0.2 and 0.5, and c which is not locked; a view showing them"""
    from spiny.annotations import get_controller
    from spiny.annotations.model import Annotation, AnnotationSet

    def tier():
        return [Annotation(0.2, 0.5, "x"), Annotation(0.5, 0.9, "y")]

    controller = get_controller()
    controller.setAnnotationModel(AnnotationSet({"a": tier(), "b": tier(), "c": tier()}, set()))
    window._visualisation_area._dock_wav.wav_plot.setXRange(0, 1, padding=0)
    process_events()
    for row in (0, 1):
        controller._list_tiers_widget.item(row).setSelected(True)
    controller.toggleTierLock()
    yield controller
    controller.setAnnotationModel(AnnotationSet({}, set()))


def rendered(controller, tier, index):
    annotation = controller.model.annotations[tier][index]
    return next(i for i in controller.view.tiers_dict[tier].annotation_items if i._segment is annotation)


def bounds(controller, tier):
    return [(round(a.start_time, 4), round(a.end_time, 4)) for a in controller.model.annotations[tier]]


def test_lock_marks_the_tiers_and_toggles(two_locked_tiers):
    from spiny.gui import theme

    controller = two_locked_tiers
    assert controller.model.locked == {"a", "b"}
    assert controller.view.tiers_dict["a"].getViewBox().state["background"] == theme.color("tier_locked")
    assert controller.view.tiers_dict["c"].getViewBox().state["background"] == theme.color("tier_background")
    assert not controller._list_tiers_widget.item(0).icon().isNull()
    assert controller._list_tiers_widget.item(2).icon().isNull()

    for row in (0, 1):
        controller._list_tiers_widget.item(row).setSelected(True)
    controller.toggleTierLock()
    assert controller.model.locked == set()
    assert controller._list_tiers_widget.item(0).icon().isNull()


def test_moving_a_boundary_moves_the_aligned_ones_of_the_locked_tiers(two_locked_tiers):
    controller = two_locked_tiers
    rendered(controller, "a", 0).lines[1].setValue(0.6)  # the same as dragging it with the mouse
    # In the other locked tier, both annotations which share the boundary follow
    assert bounds(controller, "b") == [(0.2, 0.6), (0.6, 0.9)]
    assert rendered(controller, "b", 0).lines[1].value() == pytest.approx(0.6)
    assert rendered(controller, "b", 1).lines[0].value() == pytest.approx(0.6)
    # A tier which is not locked does not change
    assert bounds(controller, "c") == [(0.2, 0.5), (0.5, 0.9)]
    # In the tier itself, only the item which has been moved changes
    assert bounds(controller, "a") == [(0.2, 0.6), (0.5, 0.9)]


def test_dragging_a_whole_annotation_with_the_mouse_moves_both_boundaries(window, two_locked_tiers):
    from pyqtgraph.Qt import QtTest

    controller = two_locked_tiers
    tiers = window._visualisation_area._dock_annotation
    plot = tiers.tiers_dict["a"]
    tiers.scroll.ensureWidgetVisible(plot)
    process_events()

    def position(time_position):
        return plot.mapFromScene(plot.getViewBox().mapViewToScene(QtCore.QPointF(time_position, 0.5)))

    viewport = plot.viewport()
    left = QtCore.Qt.MouseButton.LeftButton
    start, end = position(0.35), position(0.4)
    QtTest.QTest.mousePress(viewport, left, pos=start)
    for fraction in (0.25, 0.5, 0.75, 1.0):
        point = QtCore.QPointF(start + (end - start) * fraction)
        event = QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseMove,
            point,
            QtCore.QPointF(viewport.mapToGlobal(point)),
            QtCore.Qt.MouseButton.NoButton,
            left,
            QtCore.Qt.KeyboardModifier.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(viewport, event)
    QtTest.QTest.mouseRelease(viewport, left, pos=end)
    QtWidgets.QApplication.processEvents()

    moved_start, moved_end = (
        controller.model.annotations["a"][0].start_time,
        controller.model.annotations["a"][0].end_time,
    )
    assert moved_start == pytest.approx(0.25, abs=0.01) and moved_end == pytest.approx(0.55, abs=0.01)
    assert bounds(controller, "b")[0] == pytest.approx((round(moved_start, 4), round(moved_end, 4)))


def test_several_steps_of_a_drag_stay_aligned(two_locked_tiers):
    controller = two_locked_tiers
    line = rendered(controller, "a", 0).lines[0]
    for position in (0.22, 0.25, 0.3, 0.28):
        line.setValue(position)
        assert bounds(controller, "b")[0][0] == pytest.approx(position)


def test_editing_the_times_moves_the_aligned_boundaries(two_locked_tiers):
    controller = two_locked_tiers
    controller.update_current_annotation(rendered(controller, "a", 0))
    controller._wEndTime.setText("0.7")
    controller.onTimeEdited()
    assert bounds(controller, "b")[0] == (0.2, 0.7)


def test_a_boundary_which_is_not_aligned_does_not_move(two_locked_tiers):
    controller = two_locked_tiers
    controller.model.annotations["b"][0].end_time = 0.55
    rendered(controller, "b", 0).setBounds(0.2, 0.55)
    rendered(controller, "a", 0).lines[1].setValue(0.6)
    assert bounds(controller, "b")[0] == (0.2, 0.55)


def test_a_move_which_would_collapse_an_annotation_is_not_applied_to_it(two_locked_tiers):
    controller = two_locked_tiers
    controller.model.annotations["b"][0].end_time = 0.3
    rendered(controller, "b", 0).setBounds(0.2, 0.3)
    rendered(controller, "a", 0).lines[0].setValue(0.35)
    assert bounds(controller, "b")[0] == (0.2, 0.3)


def test_moving_boundaries_reaches_annotations_which_are_not_drawn(two_locked_tiers, window):
    from spiny.annotations.model import Annotation

    controller = two_locked_tiers
    hidden = Annotation(0.6, 0.7, "far")
    controller.model.annotations["b"].append(hidden)
    controller.view.tiers_dict["b"].moveBoundaries([(0.6, 0.65)])
    assert hidden.start_time == 0.65


def test_locked_moves_count_as_unsaved_changes(two_locked_tiers, window, monkeypatch):
    controller = two_locked_tiers
    asked = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        lambda *a, **k: asked.append(a) or QtWidgets.QMessageBox.StandardButton.Cancel,
    )
    controller._saved_contents = controller._contents()
    rendered(controller, "a", 0).lines[1].setValue(0.6)
    assert not controller.confirmDiscardChanges() and asked


def toolbar_of(window):
    from spiny.annotations import AnnotationToolBar

    return window.findChild(AnnotationToolBar)


def test_toolbar_adds_an_annotation_from_the_playhead_and_removes_it(window, two_locked_tiers):
    from spiny.core import player

    controller = two_locked_tiers
    bar = toolbar_of(window)
    player.seek(0.05)
    controller._list_tiers_widget.item(2).setSelected(True)
    bar.buttons["add_annotation"].click()
    annotation = controller.model.annotations["c"][0]
    # From the playhead, until the next annotation: the selected tier is c
    assert annotation.start_time == pytest.approx(0.05) and annotation.end_time == pytest.approx(0.2)
    assert controller._current_annotation._segment is annotation

    bar.buttons["remove_annotation"].click()
    assert annotation not in controller.model.annotations["c"]
    assert controller._current_annotation is None
    controller._list_tiers_widget.item(2).setSelected(False)
    player.seek(0.0)


def test_toolbar_adds_an_annotation_on_the_waveform_selection(window, two_locked_tiers):
    from spiny.core import player
    from spiny.core.segment import Segment
    from spiny.gui.items import SegmentItem

    controller = two_locked_tiers
    view = window._visualisation_area._dock_wav.wav_plot.getViewBox()
    item = SegmentItem(Segment(1.0, 1.5))
    view._dragPoint = item
    try:
        toolbar_of(window).buttons["add_annotation"].click()
        tier = controller.model.annotations["a"]
        assert (tier[-1].start_time, tier[-1].end_time) == (1.0, min(1.5, player.duration))
    finally:
        view._dragPoint = None


def test_toolbar_refuses_an_annotation_where_there_is_no_room(window, two_locked_tiers):
    from spiny.core import player

    controller = two_locked_tiers
    window.dialogs.clear()
    player.seek(0.3)  # inside an annotation
    before = list(controller.model.annotations["a"])
    toolbar_of(window).buttons["add_annotation"].click()
    assert controller.model.annotations["a"] == before and window.dialogs
    window.dialogs.clear()
    player.seek(0.0)


def test_toolbar_explains_when_nothing_is_selected(window, two_locked_tiers):
    window.dialogs.clear()
    bar = toolbar_of(window)
    for name in ("remove_tier", "remove_annotation", "lock"):
        bar.buttons[name].click()
    assert len(window.dialogs) == 3
    window.dialogs.clear()


def test_toolbar_removes_the_selected_tiers_and_their_lock(window, two_locked_tiers):
    controller = two_locked_tiers
    controller._list_tiers_widget.item(0).setSelected(True)
    toolbar_of(window).buttons["remove_tier"].click()
    assert "a" not in controller.model.annotations and "a" not in controller.model.locked


def test_toolbar_adds_a_tier(window, two_locked_tiers, monkeypatch):
    controller = two_locked_tiers
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *a, **k: ("new", True))
    toolbar_of(window).buttons["add_tier"].click()
    assert "new" in controller.model.annotations and "new" in controller.view.tiers_dict


@pytest.fixture
def history(window):
    """Tiers a and b, with a clean history; the view shows them"""
    from spiny.annotations import get_controller
    from spiny.annotations.model import Annotation, AnnotationSet

    def tier():
        return [Annotation(0.2, 0.5, "x"), Annotation(0.5, 0.9, "y")]

    controller = get_controller()
    controller.setAnnotationModel(AnnotationSet({"a": tier(), "b": tier()}, set()))
    window._visualisation_area._dock_wav.wav_plot.setXRange(0, 1, padding=0)
    process_events()
    yield controller
    controller.setAnnotationModel(AnnotationSet({}, set()))


def state(controller):
    return controller._snapshot()


def check_undo_redo(controller, operation):
    """The operation is one step, which undo removes and redo brings back"""
    before = state(controller)
    operation()
    process_events()
    after = state(controller)
    assert after != before
    assert len(controller._undo_stack) == 2
    controller.undo()
    process_events()
    assert state(controller) == before and controller.can_redo
    controller.redo()
    process_events()
    assert state(controller) == after and not controller.can_redo


def test_undo_adding_a_tier(window, history, monkeypatch):
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *a, **k: ("new", True))
    check_undo_redo(history, history._add_tier)
    assert "new" in history.view.tiers_dict
    assert [history._list_tiers_widget.item(r).text() for r in range(3)] == ["a", "b", "new"]


def test_undo_removing_a_tier(history):
    def remove():
        history._list_tiers_widget.item(0).setSelected(True)
        history.removeSelectedTiers()

    check_undo_redo(history, remove)


def test_undo_hiding_and_locking_tiers(history):
    def hide():
        history._list_tiers_widget.item(0).setSelected(True)
        history._toggle_tier()

    check_undo_redo(history, hide)
    assert not history.view.tiers_dict["a"].isVisibleTo(history.view) and "a" in history.model.ignored
    history.undo()
    assert history.view.tiers_dict["a"].isVisibleTo(history.view)

    history.setAnnotationModel(type(history.model)(dict(history.model.annotations), set()))

    def lock():
        history._list_tiers_widget.item(0).setSelected(True)
        history.toggleTierLock()

    check_undo_redo(history, lock)
    assert not history._list_tiers_widget.item(0).icon().isNull()


def test_undo_reordering_tiers(history):
    def reorder():
        widget = history._list_tiers_widget
        item = widget.takeItem(0)
        widget.addItem(item)
        history._update_order()

    check_undo_redo(history, reorder)
    assert list(history.model.annotations) == ["b", "a"]
    history.undo()
    assert list(history.model.annotations) == ["a", "b"]


def test_undo_adding_and_removing_annotations(window, history):
    from spiny.core import player

    player.seek(0.05)
    check_undo_redo(history, history.addAnnotation)
    player.seek(0.0)
    history.update_current_annotation(rendered(history, "a", 1))

    before = len(history._undo_stack)
    history.removeCurrentAnnotation()
    assert len(history._undo_stack) == before + 1
    history.undo()
    assert len(history.model.annotations["a"]) == 3


def test_a_drag_is_one_step_and_includes_the_locked_tiers(window, history):
    for row in (0, 1):
        history._list_tiers_widget.item(row).setSelected(True)
    history.toggleTierLock()
    before = len(history._undo_stack)

    item = rendered(history, "a", 0)
    for position in (0.52, 0.55, 0.6):
        item.lines[1].setValue(position)  # several mouse events
    item.lineMoveFinished()
    assert len(history._undo_stack) == before + 1
    assert history.model.annotations["b"][0].end_time == pytest.approx(0.6)

    history.undo()
    assert bounds(history, "a") == [(0.2, 0.5), (0.5, 0.9)] and bounds(history, "b") == [(0.2, 0.5), (0.5, 0.9)]
    assert rendered(history, "a", 0).lines[1].value() == pytest.approx(0.5)


def test_undo_typing_a_time(history):
    def edit():
        history.update_current_annotation(rendered(history, "a", 0))
        history._wEndTime.setText("0.45")
        history.onTimeEdited()

    check_undo_redo(history, edit)


def test_a_typed_label_is_one_step(history):
    from pyqtgraph.Qt import QtTest

    history.update_current_annotation(rendered(history, "a", 0))
    before = len(history._undo_stack)
    QtTest.QTest.keyClicks(history._wLabel, "abc")
    assert len(history._undo_stack) == before  # nothing yet while typing
    QtTest.QTest.keyClick(history._wLabel, QtCore.Qt.Key.Key_Return)
    assert len(history._undo_stack) == before + 1 and history.model.annotations["a"][0].label == "xabc"
    history.undo()
    assert history.model.annotations["a"][0].label == "x"


def test_label_being_typed_is_undone_too(history):
    from pyqtgraph.Qt import QtTest

    history.update_current_annotation(rendered(history, "a", 0))
    QtTest.QTest.keyClicks(history._wLabel, "z")
    history.undo()  # no Enter before
    assert history.model.annotations["a"][0].label == "x"


def test_a_new_operation_forgets_what_could_be_redone(window, history):
    history.model.annotations["a"][0].label = "changed"
    history.commit()
    history.undo()
    assert history.can_redo
    history.model.annotations["a"][0].label = "other"
    history.commit()
    assert not history.can_redo


def test_history_is_limited_and_forgets_on_load(history):
    from spiny.annotations.control import MAX_UNDO_STEPS
    from spiny.annotations.model import Annotation, AnnotationSet

    for index in range(MAX_UNDO_STEPS + 20):
        history.model.annotations["a"][0].label = str(index)
        history.commit()
    assert len(history._undo_stack) == MAX_UNDO_STEPS + 1

    history.setAnnotationModel(AnnotationSet({"t": [Annotation(0, 1, "x")]}, set()))
    assert not history.can_undo and not history.can_redo


def test_unchanged_tiers_share_their_memory(history):
    history.model.annotations["a"][0].label = "changed"
    history.commit()
    previous, current = history._undo_stack[-2], history._undo_stack[-1]
    assert dict(previous[0])["b"] is dict(current[0])["b"]
    assert dict(previous[0])["a"] is not dict(current[0])["a"]


def test_undo_back_to_the_saved_state_has_nothing_to_save(window, history, monkeypatch):
    asked = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", lambda *a, **k: asked.append(a))
    history.model.annotations["a"][0].label = "changed"
    history.commit()
    history.undo()
    assert history.confirmDiscardChanges() and not asked


def test_undo_entries_of_the_edit_menu_follow_the_history(window, history):
    assert "undo" not in toolbar_of(window).buttons
    undo, redo = window._undo_action, window._redo_action
    assert not undo.isEnabled() and not redo.isEnabled()
    history.model.annotations["a"][0].label = "changed"
    history.commit()
    assert undo.isEnabled() and not redo.isEnabled()
    undo.trigger()
    assert history.model.annotations["a"][0].label == "x"
    assert not undo.isEnabled() and redo.isEnabled()
    redo.trigger()
    assert history.model.annotations["a"][0].label == "changed"


def menu_entries(window, title):
    menu = next(a.menu() for a in window.menuBar().actions() if a.text().replace("&", "") == title)
    return {a.text().replace("&", ""): a for a in menu.actions()}


def test_menus(window):
    assert list(menu_entries(window, "Edit")) == ["Undo", "Redo"]
    assert set(menu_entries(window, "Help")) == {"Keyboard shortcuts...", "About Sp1NY..."}


def test_about(window, monkeypatch):
    shown = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "about", lambda *a: shown.append(a[2]))
    menu_entries(window, "Help")["About Sp1NY..."].trigger()
    assert "Sp1NY" in shown[0] and "MIT" in shown[0]


@pytest.fixture
def shortcut_config(window, tmp_path, monkeypatch):
    """The configuration file is a temporary one, and the shortcuts come back at the end"""
    import spiny.config
    from spiny.gui.shortcuts import SHORTCUTS, set_shortcuts

    before = dict(SHORTCUTS)
    path = tmp_path / "spiny" / "config.yaml"
    monkeypatch.setattr(spiny.config, "_config_path", path)
    yield path
    set_shortcuts(before)


def open_shortcuts(window):
    from spiny.gui.shortcuts_dialog import ShortcutsDialog

    return ShortcutsDialog(window)


def set_key(dialog, action, key):
    dialog._editors[action].setKeySequence(key)


def test_dialog_shows_every_shortcut(window, shortcut_config):
    from spiny.gui.shortcuts import SHORTCUTS

    dialog = open_shortcuts(window)
    assert dialog._table.rowCount() == len(SHORTCUTS)
    assert {a: e.keySequence() for a, e in dialog._editors.items()} == {
        a: QtGui.QKeySequence(k) for a, k in SHORTCUTS.items()
    }


def test_editing_a_shortcut_applies_it_everywhere_and_saves_it(window, shortcut_config):
    import yaml
    from pyqtgraph.Qt import QtTest
    from spiny.core import player
    from spiny.core.wav import TransportWidget
    from spiny.gui.shortcuts import shortcut

    dialog = open_shortcuts(window)
    set_key(dialog, "loop", "Ctrl+Shift+Y")
    set_key(dialog, "undo", "Ctrl+Alt+U")
    dialog.accept()

    assert shortcut("loop").toString() == "Ctrl+Shift+Y"
    button = window.findChild(TransportWidget)._bLoop
    assert button._shortcut.key().toString() == "Ctrl+Shift+Y" and "Ctrl+Shift+Y" in button.toolTip()
    assert window._undo_action.shortcut().toString() == "Ctrl+Alt+U"
    assert yaml.safe_load(shortcut_config.read_text()) == {"shortcuts": {"loop": "Ctrl+Shift+Y", "undo": "Ctrl+Alt+U"}}

    # The new key works, and the old one does nothing anymore
    window.activateWindow()
    QtTest.QTest.qWaitForWindowActive(window, 2000)
    before = player.loop_activated
    QtTest.QTest.keyClick(window, QtCore.Qt.Key.Key_L)
    assert player.loop_activated == before
    QtTest.QTest.keyClick(
        window,
        QtCore.Qt.Key.Key_Y,
        QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.KeyboardModifier.ShiftModifier,
    )
    assert player.loop_activated != before
    player.toggleLoop()


def test_saving_shortcuts_keeps_the_other_settings(window, shortcut_config):
    import yaml

    shortcut_config.parent.mkdir(parents=True)
    shortcut_config.write_text("theme: dark\nwheel:\n  wheel_up_down: pan\nshortcuts:\n  mute: X\n")
    dialog = open_shortcuts(window)
    set_key(dialog, "loop", "Ctrl+Y")
    dialog.accept()
    assert yaml.safe_load(shortcut_config.read_text()) == {
        "theme": "dark",
        "wheel": {"wheel_up_down": "pan"},
        "shortcuts": {"loop": "Ctrl+Y"},
    }
    assert not list(shortcut_config.parent.glob("*.tmp"))


def test_two_actions_cannot_get_the_same_shortcut(window, shortcut_config):
    from spiny.gui.shortcuts import shortcut

    window.dialogs.clear()
    dialog = open_shortcuts(window)
    set_key(dialog, "loop", "M")
    dialog.accept()
    assert window.dialogs and "mute" in window.dialogs[0][2]
    assert shortcut("loop").toString() == "L" and not shortcut_config.exists()
    window.dialogs.clear()


def test_restore_defaults_and_removing_a_shortcut(window, shortcut_config):
    import yaml
    from spiny.gui.shortcuts import DEFAULT_SHORTCUTS, set_shortcuts, shortcut

    set_shortcuts({"loop": "Ctrl+Y"})
    dialog = open_shortcuts(window)
    dialog._restoreDefaults()
    assert dialog._editors["loop"].keySequence().toString() == DEFAULT_SHORTCUTS["loop"]
    dialog._editors["mute"].clear()
    dialog.accept()
    assert shortcut("loop").toString() == "L" and shortcut("mute").isEmpty()
    assert yaml.safe_load(shortcut_config.read_text()) == {"shortcuts": {"mute": ""}}


def test_cancel_changes_nothing(window, shortcut_config):
    from spiny.gui.shortcuts import shortcut

    dialog = open_shortcuts(window)
    set_key(dialog, "loop", "Ctrl+Y")
    dialog.reject()
    assert shortcut("loop").toString() == "L" and not shortcut_config.exists()


def test_a_broken_configuration_file_is_not_overwritten(window, shortcut_config):
    from spiny.gui.shortcuts import shortcut

    shortcut_config.parent.mkdir(parents=True)
    shortcut_config.write_text("{not yaml")
    window.dialogs.clear()
    dialog = open_shortcuts(window)
    set_key(dialog, "loop", "Ctrl+Y")
    dialog.accept()
    assert shortcut("loop").toString() == "Ctrl+Y"  # applied for this session
    assert shortcut_config.read_text() == "{not yaml" and window.dialogs
    window.dialogs.clear()
