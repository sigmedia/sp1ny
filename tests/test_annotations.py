import json
import pathlib

import pytest
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

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
