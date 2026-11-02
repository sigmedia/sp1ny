import json
import pathlib

import pytest
from pyqtgraph.Qt import QtCore, QtGui, QtTest, QtWidgets

from spiny.annotations.model import Annotation


@pytest.fixture
def controller(player):
    from spiny.annotations import get_controller

    controller = get_controller()
    controller.update_current_annotation(None)
    return controller


@pytest.fixture
def tier(controller, example_annotations):
    from spiny.annotations.visualisation import TierPlot

    plot = TierPlot(tier_name="default", model=example_annotations, handle_segment=controller.update_current_annotation)
    plot.resize(800, 100)
    plot.show()
    plot.setXRange(0, 0.5)
    QtWidgets.QApplication.processEvents()
    yield plot
    controller.update_current_annotation(None)
    plot.close()


def test_loaded_annotations_are_selectable(tier):
    assert tier.annotation_items
    assert all(item._handle_edit is not None for item in tier.annotation_items)


def test_selection_is_owned_by_the_controller(controller, tier):
    a, b = tier.annotation_items[:2]
    a.requestSelection()
    b.requestSelection()
    assert (a.isSelected(), b.isSelected(), controller._current_annotation) == (False, True, b)
    b.requestSelection()  # clicking the current item unselects it
    assert (a.isSelected(), b.isSelected(), controller._current_annotation) == (False, False, None)


def test_new_annotation_is_not_duplicated_by_panning(controller, tier, example_annotations):
    from spiny.annotations.visualisation import AnnotationItem

    annotation = Annotation(0.45, 0.49, "new")
    example_annotations.annotations["default"].append(annotation)
    item = AnnotationItem(annotation, True, controller.update_current_annotation)
    tier.addItem(item)
    tier._items[id(annotation)] = item
    item.requestSelection()

    tier.setXRange(0.3, 0.6)
    tier.setXRange(0, 0.5)
    rendered = [x for x in tier.getPlotItem().items if isinstance(x, AnnotationItem) and x._segment is annotation]
    assert rendered == [item]


def test_delete_key(controller, tier, example_annotations):
    delete = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Delete, QtCore.Qt.NoModifier)
    n = len(example_annotations.annotations["default"])
    tier.keyPressEvent(delete)  # nothing selected: no-op
    assert len(example_annotations.annotations["default"]) == n

    victim = tier.annotation_items[0]
    victim.requestSelection()
    tier.keyPressEvent(delete)
    assert len(example_annotations.annotations["default"]) == n - 1
    assert victim not in tier.annotation_items
    assert controller._current_annotation is None


@pytest.mark.parametrize("start, end", [("", "0.2"), ("0.5", "0.1"), ("-1", "0.2")])
def test_invalid_time_edition_is_reverted(controller, tier, start, end):
    item = tier.annotation_items[0]
    item.requestSelection()
    before = (item._segment.start_time, item._segment.end_time)
    controller._wStartTime.setText(start)
    controller._wEndTime.setText(end)
    controller.onTimeEdited()
    assert (item._segment.start_time, item._segment.end_time) == before
    assert controller._wStartTime.text() == f"{before[0]:.4f}"


def test_valid_time_edition(controller, tier):
    item = tier.annotation_items[0]
    item.requestSelection()
    controller._wStartTime.setText("0.01")
    controller._wEndTime.setText("0.2")
    controller.onTimeEdited()
    assert (item._segment.start_time, item._segment.end_time) == (0.01, 0.2)


@pytest.fixture
def view(controller, tmp_path):
    """Controller attached to a real annotation dock, with two tiers loaded"""
    from spiny.annotations.visualisation import AnnotationDock
    from spiny.core.wav.visualisation import WavDock

    wav = WavDock("Signal", (10, 10))
    dock = AnnotationDock("Annotations", (10, 10), wav.wav_plot)
    controller.setView(dock)
    f = tmp_path / "t.json"
    one = [{"start_time": 0, "end_time": 1, "label": "a"}]
    f.write_text(json.dumps({"annotations": {"t1": one, "t2": one}}))
    controller.loadAnnotations(f)
    yield dock
    controller.setView(None)


def test_hidden_tier_stays_hidden(controller, view):
    tiers = controller._list_tiers_widget
    tiers.item(0).setSelected(True)
    controller._toggle_tier()
    hidden = lambda: not view.tiers_dict["t1"].isVisibleTo(view.widget)  # noqa: E731
    assert hidden() and controller.model.ignored == {"t1"}

    tiers.item(1).setSelected(True)
    tiers.item(1).setSelected(False)
    controller.resetView()
    assert hidden()

    tiers.item(0).setSelected(True)
    controller._toggle_tier()
    assert not hidden() and controller.model.ignored == set()


def test_add_and_remove_tiers(controller, view, monkeypatch, no_dialogs):
    for name in ("  ", "t1"):  # empty and duplicate names are rejected
        monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *a, _n=name, **k: (_n, True))
        controller._add_tier()
    assert list(controller.model.annotations) == ["t1", "t2"] and len(no_dialogs) == 2

    controller._list_tiers_widget.item(0).setSelected(True)
    controller._toggle_tier()
    controller._list_tiers_widget.selectAll()
    controller._remove_tiers()
    assert dict(controller.model.annotations) == {} and controller.model.ignored == set()


def test_save_uses_the_chosen_format(controller, view, tmp_path, monkeypatch, no_dialogs):
    dialog = QtWidgets.QFileDialog
    monkeypatch.setattr(dialog, "getSaveFileName", lambda *a, **k: ("", ""))
    controller._save_annotation_file()  # cancelled: nothing happens

    monkeypatch.setattr(
        dialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "o.TextGrid"), "JSON Files (*.json)")
    )
    controller._save_annotation_file()
    assert (tmp_path / "o.TextGrid").read_text().startswith("File type")

    monkeypatch.setattr(dialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "noext"), "JSON Files (*.json)"))
    controller._save_annotation_file()
    assert (tmp_path / "noext.json").exists()
    assert no_dialogs == []


def test_load_errors_are_reported(controller, view, monkeypatch, no_dialogs):
    dialog = QtWidgets.QFileDialog
    monkeypatch.setattr(dialog, "getOpenFileName", lambda *a, **k: ("", ""))
    controller._load_annotation_file()
    monkeypatch.setattr(dialog, "getOpenFileName", lambda *a, **k: (str(pathlib.Path("unknown.wav")), ""))
    controller._load_annotation_file()
    assert [name for name, _ in no_dialogs] == ["critical"]


def test_annotation_label_is_readable_in_every_theme(qapp):
    from spiny.annotations.model import Annotation
    from spiny.annotations.visualisation import AnnotationItem
    from spiny.gui.theme import THEMES, apply_theme, color

    item = AnnotationItem(Annotation(0.1, 0.2, "a"))
    try:
        for name in THEMES:
            apply_theme(name)
            item.applyTheme()
            assert item.brush.color() == color("annotation")
            assert item._text.textItem.defaultTextColor() == color("annotation_text")
            assert color("annotation") != color("annotation_text")
    finally:
        apply_theme("light")


def test_hidden_tier_keeps_a_readable_text_colour(qapp):
    from pyqtgraph.Qt import QtCore
    from spiny.annotations.control import QListWidgetItemHideable
    from spiny.gui.theme import color

    item = QListWidgetItemHideable()
    item.toggleTierHidden()
    assert item.foreground().color() == color("hidden_tier_text")
    item.toggleTierHidden()
    assert item.background().style() == QtCore.Qt.BrushStyle.NoBrush
    assert item.foreground().style() == QtCore.Qt.BrushStyle.NoBrush


def test_failed_save_keeps_the_existing_file(controller, tmp_path, monkeypatch):
    from spiny.annotations.io.json import JSONSerialiser

    target = tmp_path / "a.json"
    target.write_text("precious")

    def failing_save(self, output_file, annotations):
        pathlib.Path(output_file).write_text("half of the fi")
        raise OSError("disk full")

    monkeypatch.setattr(JSONSerialiser, "save", failing_save)
    with pytest.raises(OSError):
        controller._writeFile(JSONSerialiser(), target)
    assert target.read_text() == "precious"
    assert [path.name for path in tmp_path.iterdir()] == ["a.json"]


def test_save_replaces_the_target_of_a_link_and_keeps_its_permissions(controller, tmp_path):
    from spiny.annotations.io.json import JSONSerialiser

    target = tmp_path / "a.json"
    target.write_text("old")
    target.chmod(0o640)
    link = tmp_path / "link.json"
    link.symlink_to(target)
    controller._writeFile(JSONSerialiser(), link)
    assert link.is_symlink()
    assert "annotations" in json.loads(target.read_text())
    assert target.stat().st_mode & 0o777 == 0o640


@pytest.fixture
def empty_tier(controller):
    from spiny.annotations.model import AnnotationSet
    from spiny.annotations.visualisation import TierPlot

    model = AnnotationSet({"t": []}, set())
    plot = TierPlot(tier_name="t", model=model, handle_segment=controller.update_current_annotation)
    plot.resize(800, 100)
    plot.setXRange(0, 1, padding=0)
    plot.show()
    QtWidgets.QApplication.processEvents()
    yield plot
    controller.update_current_annotation(None)
    plot.close()


def widget_position(tier, time):
    """The position in the tier widget of a time"""
    return tier.mapFromScene(tier.getViewBox().mapViewToScene(QtCore.QPointF(time, 0.5)))


def click(tier, time, button=QtCore.Qt.MouseButton.LeftButton):
    QtTest.QTest.mouseClick(tier.viewport(), button, pos=widget_position(tier, time))
    QtWidgets.QApplication.processEvents()


def times(tier):
    return [
        (pytest.approx(a.start_time, abs=0.01), pytest.approx(a.end_time, abs=0.01))
        for a in tier._model.annotations["t"]
    ]


def separate_clicks():
    """The second click of a test must not be taken for a double-click"""
    QtTest.QTest.qWait(QtWidgets.QApplication.doubleClickInterval() + 50)


def test_two_clicks_create_an_annotation_at_the_clicked_times(empty_tier, player):
    click(empty_tier, 0.7)
    assert player.position == pytest.approx(0.7, abs=0.01)
    separate_clicks()
    click(empty_tier, 0.3)
    assert times(empty_tier) == [(0.3, 0.7)]


def test_view_change_between_two_clicks_keeps_the_first_time(empty_tier):
    click(empty_tier, 0.3)
    empty_tier.setXRange(0.5, 1.5, padding=0)
    QtWidgets.QApplication.processEvents()
    separate_clicks()
    click(empty_tier, 0.9)
    assert times(empty_tier) == [(0.3, 0.9)]


def test_double_click_creates_nothing(empty_tier):
    QtTest.QTest.mouseDClick(
        empty_tier.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=widget_position(empty_tier, 0.5)
    )
    QtWidgets.QApplication.processEvents()
    assert times(empty_tier) == []
    separate_clicks()
    click(empty_tier, 0.2)  # the first click of a new annotation, not the second one of the double-click
    assert times(empty_tier) == []


def test_right_click_creates_nothing(empty_tier, monkeypatch):
    # NOTE: the context menu of the plot would block the test
    monkeypatch.setattr(empty_tier.getViewBox(), "raiseContextMenu", lambda ev: None)
    click(empty_tier, 0.2)
    separate_clicks()
    click(empty_tier, 0.6, QtCore.Qt.MouseButton.RightButton)
    assert times(empty_tier) == []


def test_click_outside_the_time_area_creates_nothing(empty_tier):
    click(empty_tier, 0.2)
    separate_clicks()
    QtTest.QTest.mouseClick(empty_tier.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(3, 3))
    QtWidgets.QApplication.processEvents()
    assert times(empty_tier) == []


def test_click_on_an_annotation_cancels_the_first_click(empty_tier):
    click(empty_tier, 0.1)
    separate_clicks()
    click(empty_tier, 0.3)
    assert len(times(empty_tier)) == 1
    empty_tier._handle_segment(None)
    separate_clicks()
    click(empty_tier, 0.6)
    separate_clicks()
    click(empty_tier, 0.2)  # on the annotation
    separate_clicks()
    click(empty_tier, 0.8)
    assert len(times(empty_tier)) == 1
