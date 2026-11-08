from __future__ import annotations

import os
import pathlib
import shutil
from collections.abc import Callable
from typing import Any

from ipapy import IPA_CHARS
from ipapy.ipachar import IPAConsonant, IPASuprasegmental, IPADiacritic, IPAVowel
from pyqtgraph import QtCore, QtGui, QtWidgets
from pyqtgraph.Qt import isQObjectAlive

from ..core import player
from ..gui import theme
from ..gui.icons import ToolBarButton, transport_icon
from ..gui.helpers.widgets import CompactList
from ..gui.widgets import CollapsibleBox
from .io import AnnotationSerialiser
from .model import Annotation, AnnotationSet
from .visualisation import AnnotationDock, AnnotationItem
from .io.htk_lab import HTKLabelSerialiser
from .io.textgrid import TextGridSerialiser
from .io.json import JSONSerialiser

# Supported annotation formats: file dialog filter => (extension, serialiser class)
ANNOTATION_FORMATS = {
    "TextGrid Files (*.TextGrid)": (".TextGrid", TextGridSerialiser),
    "HTK Label Files (*.lab)": (".lab", HTKLabelSerialiser),
    "JSON Files (*.json)": (".json", JSONSerialiser),
}
ANNOTATION_FILTERS = ";;".join(ANNOTATION_FORMATS.keys())


def serialiser_for(annotation_file: pathlib.Path) -> AnnotationSerialiser:
    """Instantiate the serialiser matching the extension of the given file (case insensitive)

    Raises
    ------
    ValueError
        if the extension is not supported
    """
    for extension, serialiser_cls in ANNOTATION_FORMATS.values():
        if annotation_file.suffix.lower() == extension.lower():
            return serialiser_cls()
    raise ValueError(f'The annotation format of "{annotation_file}" is unknown')


class QListWidgetItemHideable(QtWidgets.QListWidgetItem):
    """Tier list entry remembering whether its tier is hidden

    Notes
    -----
    The state is named "tier hidden" on purpose: QListWidgetItem.isHidden() means that the entry itself is
    hidden from the list, which is not the case here.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._hidden = False
        self._locked = False

    def setLocked(self, locked: bool) -> None:
        """Show whether the tier is locked

        Parameters
        ----------
        locked : bool
            True if it is locked
        """
        self._locked = locked
        self.applyTheme()

    def toggleTierHidden(self) -> None:
        """Hide the tier if it is shown, show it if it is hidden; a hidden tier is highlighted in the list"""
        self._hidden = not self._hidden
        self.applyTheme()

    def applyTheme(self) -> None:
        """Show the state of the tier with the colours of the current theme"""
        # NOTE: an empty brush means the colours of the palette
        self.setBackground(QtGui.QBrush(theme.color("hidden_tier")) if self._hidden else QtGui.QBrush())
        self.setForeground(QtGui.QBrush(theme.color("hidden_tier_text")) if self._hidden else QtGui.QBrush())
        self.setIcon(transport_icon("lock", theme.color("window_text")) if self._locked else QtGui.QIcon())

    def isTierHidden(self) -> bool:
        """Tell if the tier is hidden

        Returns
        -------
        bool
            True if the tier is hidden
        """
        return self._hidden


class TierList(CompactList):
    """List of the tiers, whose entries follow the theme"""

    MIN_VISIBLE_ROWS = 4

    def applyTheme(self) -> None:
        """Show the entries with the colours of the current theme"""
        for row in range(self.count()):
            self.item(row).applyTheme()


class AnnotationToolBar(QtWidgets.QWidget):
    """Toolbar of the basic operations on the annotations

    Parameters
    ----------
    controller : ControlLayout
        The annotation controller
    parent : QtWidgets.QWidget, optional
        The parent widget. (default: None)
    """

    def __init__(self, controller: ControlLayout, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)
        self.buttons = {}
        for icon, tooltip, action, slot in (
            ("add_tier", "Add a tier", "add_tier", controller._add_tier),
            ("remove_tier", "Remove the selected tiers", "remove_tier", controller.removeSelectedTiers),
            ("add_annotation", "Add an annotation", "add_annotation", controller.addAnnotation),
            (
                "remove_annotation",
                "Remove the selected annotation",
                "delete_annotation",
                controller.removeCurrentAnnotation,
            ),
            ("lock", "Lock or unlock the selected tiers", "toggle_tier_lock", controller.toggleTierLock),
            ("undo", "Undo", "undo", controller.undo),
            ("redo", "Redo", "redo", controller.redo),
        ):
            button = ToolBarButton(icon, tooltip, action)
            button.clicked.connect(slot)
            layout.addWidget(button)
            self.buttons[icon] = button

        self._controller = controller
        controller.historyChanged.connect(self._showHistory)
        self._showHistory()

    def _showHistory(self) -> None:
        """Enable the undo and redo buttons when they can do something"""
        self.buttons["undo"].setEnabled(self._controller.can_undo)
        self.buttons["redo"].setEnabled(self._controller.can_redo)


class QLabelClickable(QtWidgets.QLabel):
    """Label emitting its text when it is clicked (used by the IPA palettes)"""

    clicked = QtCore.Signal(str)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """Emit `clicked` with the text of the label

        Parameters
        ----------
        event : QtGui.QMouseEvent
            The mouse event
        """
        self.clicked.emit(self.text())


class ControlLayout(QtWidgets.QVBoxLayout):
    """Annotation tab: file loading/saving, tier list, edition of the selected annotation, IPA palettes

    The layout owns the annotation model (an AnnotationSet) and keeps the annotation dock (the view) in
    sync with it. It is also the owner of the selected annotation, see update_current_annotation.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        The parent widget
    """

    #: Emitted when what can be undone or redone changes
    historyChanged = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None) -> None:
        super().__init__(parent)

        # View and model
        self._model: AnnotationSet = AnnotationSet({}, set())
        self._saved_contents = self._contents()
        self._undo_stack = [self._snapshot()]  # NOTE: the last one is the current state
        self._redo_stack: list[Any] = []
        self._view: AnnotationDock | None = None
        self._list_registered_modules = _registered_modules

        # Create the main layout
        box_layout = QtWidgets.QVBoxLayout()
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Prepare scrollbar
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)

        # Generate the necessary widgets
        self._current_annotation: AnnotationItem | None = None
        self._file_box = self._generate_file_box()
        self._info_box = self._generate_general_box()
        self._tier_box = self._generate_tier_box()
        self._ipa_box = self._generate_IPA_box()

        # Add the widgets
        box_layout.addWidget(self._file_box)
        box_layout.addWidget(self._tier_box)
        box_layout.addWidget(self._info_box)
        box_layout.addWidget(self._ipa_box)
        box_layout.addStretch(1)  # The groups only take the height they need, from the top

        # Nothing selected => no info to show
        self._info_box.setVisible(False)

        # Generate Configuration Widget
        configuration_widget = QtWidgets.QWidget()
        configuration_widget.setLayout(box_layout)
        scroll.setWidget(configuration_widget)

        # Finalize the layout
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.addWidget(scroll)

    @property
    def list_registered_modules(self) -> set[Callable[[], None]]:
        """set(callable): Functions called (without argument) every time the annotation view is reset"""
        return self._list_registered_modules

    def _contents(self) -> tuple[list, set[str]]:
        """Give what the annotations contain, independently of the objects which are edited in place

        Returns
        -------
        list
            The (name, [(start time, end time, label), ...]) of each tier, in display order
        set(str)
            The names of the hidden tiers
        """
        tiers = [
            (name, [(annotation.start_time, annotation.end_time, annotation.label) for annotation in annotations])
            for name, annotations in self._model.annotations.items()
        ]
        return tiers, set(self._model.ignored)

    def _snapshot(self) -> tuple[list, set[str], set[str]]:
        """Give everything which can be undone

        Returns
        -------
        list
            The (name, [(start time, end time, label), ...]) of each tier, in display order
        set(str)
            The names of the hidden tiers
        set(str)
            The names of the locked tiers
        """
        return (*self._contents(), set(self._model.locked))

    @property
    def can_undo(self) -> bool:
        """bool: True if there is an operation to undo"""
        return len(self._undo_stack) > 1

    @property
    def can_redo(self) -> bool:
        """bool: True if there is an operation to redo"""
        return bool(self._redo_stack)

    def commit(self) -> None:
        """Record the current state if an operation has changed it (to be called at the end of each operation)"""
        snapshot = self._snapshot()
        previous = self._undo_stack[-1]
        if snapshot == previous:
            return
        # NOTE: the tiers which have not changed share their memory with the previous state
        unchanged = dict(previous[0])
        tiers = [(name, unchanged[name] if unchanged.get(name) == values else values) for name, values in snapshot[0]]
        self._undo_stack.append((tiers, snapshot[1], snapshot[2]))
        del self._undo_stack[: -MAX_UNDO_STEPS - 1]
        self._redo_stack.clear()
        self.historyChanged.emit()

    def undo(self) -> None:
        """Undo the last operation"""
        self.commit()  # NOTE: a label being typed is an operation too
        if self.can_undo:
            self._redo_stack.append(self._undo_stack.pop())
            self._restore(self._undo_stack[-1])

    def redo(self) -> None:
        """Redo the last operation which has been undone"""
        self.commit()
        if self.can_redo:
            self._undo_stack.append(self._redo_stack.pop())
            self._restore(self._undo_stack[-1])

    def _restore(self, snapshot: tuple[list, set[str], set[str]]) -> None:
        """Go back to a recorded state

        Parameters
        ----------
        snapshot : tuple
            The state, see `_snapshot`
        """
        tiers, ignored, locked = snapshot
        self._model.annotations = {name: [Annotation(*values) for values in annotations] for name, annotations in tiers}
        self._model.ignored = set(ignored)
        self._model.locked = set(locked)
        self.resetView()
        self.updateTierList()
        self.historyChanged.emit()

    def confirmDiscardChanges(self) -> bool:
        """If there are unsaved annotations, ask whether to save them, to discard them or to cancel

        Returns
        -------
        bool
            True if what was going to replace the annotations can go on
        """
        if self._contents() == self._saved_contents:
            return True

        Button = QtWidgets.QMessageBox.StandardButton
        answer = QtWidgets.QMessageBox.question(
            self._file_box,
            "Unsaved annotations",
            "The annotations have unsaved changes. Save them?",
            Button.Save | Button.Discard | Button.Cancel,
            Button.Save,
        )
        if answer == Button.Save:
            return self._save_annotation_file()
        return answer == Button.Discard

    def setView(self, annotation_dock: AnnotationDock) -> None:
        """Define the dock rendering the annotations

        Parameters
        ----------
        annotation_dock : AnnotationDock
            The dock
        """
        self._view = annotation_dock

    def _generate_file_box(self) -> QtWidgets.QGroupBox:
        """Create the box showing the current annotation file, with the load and save buttons

        Returns
        -------
        QtWidgets.QGroupBox
            The box
        """
        file_box_layout = QtWidgets.QGridLayout()
        file_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Start time
        l1 = QtWidgets.QLabel("Current File")
        self._wCurrentFile = QtWidgets.QLineEdit("none")
        self._wCurrentFile.setEnabled(False)
        file_box_layout.addWidget(l1, 1, 0)
        file_box_layout.addWidget(self._wCurrentFile, 1, 1)

        self._bLoadFile = QtWidgets.QPushButton("Load File")
        self._bLoadFile.clicked.connect(self._load_annotation_file)
        self._bLoadFile.setDefault(False)
        self._bLoadFile.setAutoDefault(False)
        file_box_layout.addWidget(self._bLoadFile)

        self._bSaveFile = QtWidgets.QPushButton("Save File")
        self._bSaveFile.clicked.connect(self._save_annotation_file)
        self._bSaveFile.setDefault(False)
        self._bSaveFile.setAutoDefault(False)
        file_box_layout.addWidget(self._bSaveFile)

        file_box = QtWidgets.QGroupBox("Annotation File")
        file_box.setLayout(file_box_layout)

        return file_box

    def _generate_tier_box(self) -> QtWidgets.QGroupBox:
        """Create the box listing the tiers, with the add/remove/hide buttons

        The list can be reordered by drag and drop.

        Returns
        -------
        QtWidgets.QGroupBox
            The box
        """
        tier_box = QtWidgets.QGroupBox("List of tiers")
        tier_box_layout = QtWidgets.QVBoxLayout()
        tier_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Gerate menu
        buttons_layout = QtWidgets.QHBoxLayout()
        self._add_button = QtWidgets.QPushButton("+", tier_box)
        buttons_layout.addWidget(self._add_button)
        self._add_button.clicked.connect(self._add_tier)

        self._remove_button = QtWidgets.QPushButton("-", tier_box)
        buttons_layout.addWidget(self._remove_button)
        self._remove_button.clicked.connect(self._remove_tiers)

        self._hide_button = QtWidgets.QPushButton("hide/show", tier_box)
        buttons_layout.addWidget(self._hide_button)
        self._hide_button.clicked.connect(self._toggle_tier)
        tier_box_layout.addLayout(buttons_layout)

        # Add the list
        self._list_tiers_widget = TierList(tier_box)
        self._list_tiers_widget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self._list_tiers_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self._list_tiers_widget.model().rowsMoved.connect(self._update_order)
        tier_box_layout.addWidget(self._list_tiers_widget)
        tier_box.setLayout(tier_box_layout)

        return tier_box

    def _toggle_tier(self) -> None:
        """Hide the selected tiers which are shown and show the selected tiers which are hidden"""
        # Remove from the model
        for idx, item in enumerate(self._list_tiers_widget.selectedItems()):
            item.toggleTierHidden()
            if item.isTierHidden():
                self._model.ignored.add(item.text())
            else:
                self._model.ignored.discard(item.text())
            if self.view is not None:
                self.view.tiers_dict[item.text()].setVisible(not item.isTierHidden())

            item.setSelected(False)
        self.commit()

    def _update_order(self) -> None:
        """Reorder the tiers of the model as in the list (after a drag and drop) and redraw them"""
        new_order = dict()
        for item_idx in range(self._list_tiers_widget.count()):
            item = self._list_tiers_widget.item(item_idx)
            new_order[item.text()] = self._model.annotations[item.text()]
            item.setSelected(False)

        self._model.annotations = new_order

        self.resetView()
        self.commit()

    def _remove_tiers(self) -> None:
        """Remove the selected tiers from the model and the list, and redraw the tiers"""

        # Remove from the model
        list_index = []
        for item in self._list_tiers_widget.selectedItems():
            del self._model.annotations[item.text()]
            self._model.ignored.discard(item.text())
            self._model.locked.discard(item.text())
            list_index.append(self._list_tiers_widget.row(item))
        list_index.sort()

        while list_index:
            idx = list_index.pop()
            self._list_tiers_widget.takeItem(idx)

        self.resetView()
        self.commit()

    def toggleTierLock(self) -> None:
        """Unlock the selected tiers if they are all locked, otherwise lock them"""
        items = self._list_tiers_widget.selectedItems()
        if not items:
            self._inform("Select the tiers to lock or unlock in the list of tiers.")
            return

        names = {item.text() for item in items}
        unlock = names <= self._model.locked
        self._model.locked = self._model.locked - names if unlock else self._model.locked | names
        for item in items:
            item.setLocked(not unlock)
            item.setSelected(False)
            if self.view is not None:
                self.view.tiers_dict[item.text()].applyTheme()
        self.commit()

    def removeSelectedTiers(self) -> None:
        """Remove the tiers selected in the list"""
        if self._list_tiers_widget.selectedItems():
            self._remove_tiers()
        else:
            self._inform("Select the tiers to remove in the list of tiers.")

    def addAnnotation(self) -> None:
        """Add an annotation on the waveform selection, or from the playhead (in the selected or the first tier)"""
        if self.view is None or not self.view.tiers_dict:
            self._inform("Add a tier first.")
            return

        selected = self._list_tiers_widget.selectedItems()
        tier_name = selected[0].text() if selected else self._currentTierName()
        tier = self._model.annotations[tier_name]
        selection = self.view.waveform_selection
        if selection is not None:
            start_time, end_time = max(selection[0], 0.0), min(selection[1], player.duration)
        else:
            start_time = player.position
            following = [annotation.start_time for annotation in tier if annotation.start_time > start_time]
            end_time = min(start_time + DEFAULT_ANNOTATION_DURATION, player.duration, *following)

        if end_time <= start_time or any(a.start_time < end_time and start_time < a.end_time for a in tier):
            self._inform(f'There is no room for a new annotation here in the tier "{tier_name}".')
            return
        self.view.tiers_dict[tier_name].addAnnotation(start_time, end_time)

    def removeCurrentAnnotation(self) -> None:
        """Remove the selected annotation"""
        if self.view is None or self._current_annotation is None:
            self._inform("Select the annotation to remove.")
            return
        for tier_plot in self.view.tiers_dict.values():
            tier_plot.deleteSelectedAnnotation()

    def _currentTierName(self) -> str:
        """Give the tier of the selected annotation, otherwise the first visible tier

        Returns
        -------
        str
            The name of the tier
        """
        assert self.view is not None
        tiers = self.view.tiers_dict
        for name, tier_plot in tiers.items():
            if self._current_annotation in tier_plot.annotation_items:
                return name
        visible = [name for name in tiers if name not in self._model.ignored]
        return visible[0] if visible else next(iter(tiers))

    def _inform(self, message: str) -> None:
        """Tell why an operation of the toolbar cannot be done

        Parameters
        ----------
        message : str
            The message
        """
        QtWidgets.QMessageBox.information(self._tier_box, "Annotations", message)

    def _add_tier(self) -> None:
        """Ask for the name of a new (empty) tier and add it; empty and existing names are refused"""
        tier_name, ok = QtWidgets.QInputDialog.getText(self._tier_box, "New tier", "Enter the name of the tier:")
        if not ok:
            return

        tier_name = tier_name.strip()
        if not tier_name:
            QtWidgets.QMessageBox.warning(self._tier_box, "New tier", "The name of the tier cannot be empty.")
            return
        if tier_name in self._model.annotations:
            QtWidgets.QMessageBox.warning(self._tier_box, "New tier", f'A tier named "{tier_name}" already exists.')
            return

        self._model.annotations[tier_name] = []
        item = QListWidgetItemHideable(self._list_tiers_widget)
        item.setText(tier_name)
        self.resetView()
        self._list_tiers_widget.addItem(item)
        self.commit()

    def _generate_general_box(self) -> QtWidgets.QGroupBox:
        """Create the box editing the boundaries and the label of the selected annotation

        Returns
        -------
        QtWidgets.QGroupBox
            The box
        """
        annotation_info_box_layout = QtWidgets.QGridLayout()
        annotation_info_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Start time
        l1 = QtWidgets.QLabel("Start Time (s)")
        self._wStartTime = QtWidgets.QLineEdit("-1")
        self._wStartTime.setValidator(QtGui.QDoubleValidator(0.0, float("inf"), 4, self._wStartTime))
        self._wStartTime.editingFinished.connect(self.onTimeEdited)
        annotation_info_box_layout.addWidget(l1, 1, 0)
        annotation_info_box_layout.addWidget(self._wStartTime, 1, 1)

        # End time
        l2 = QtWidgets.QLabel("End Time (s)")
        self._wEndTime = QtWidgets.QLineEdit("-1")
        self._wEndTime.setValidator(QtGui.QDoubleValidator(0.0, float("inf"), 4, self._wEndTime))
        self._wEndTime.editingFinished.connect(self.onTimeEdited)
        annotation_info_box_layout.addWidget(l2, 2, 0)
        annotation_info_box_layout.addWidget(self._wEndTime, 2, 1)

        # Label
        l3 = QtWidgets.QLabel("Label")
        self._wLabel = QtWidgets.QLineEdit("<unknown>")
        self._wLabel.textEdited.connect(self.onLabelEdited)
        self._wLabel.editingFinished.connect(self.commit)
        annotation_info_box_layout.addWidget(l3, 3, 0)
        annotation_info_box_layout.addWidget(self._wLabel, 3, 1)

        annotation_info_box = QtWidgets.QGroupBox("Current Annotation")
        annotation_info_box.setLayout(annotation_info_box_layout)

        return annotation_info_box

    def _generate_IPA_box(self) -> QtWidgets.QGroupBox:
        """Create the IPA palettes: clicking a symbol inserts it in the label of the selected annotation

        Returns
        -------
        QtWidgets.QGroupBox
            The box containing one collapsible palette per IPA category
        """

        ipa_box_layout = QtWidgets.QVBoxLayout()
        ipa_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # One collapsible palette per IPA category: (title, IPA class, font (None = default))
        categories = [
            ("Consonnants", IPAConsonant, None),
            ("Vowels", IPAVowel, None),
            ("Diacritics", IPADiacritic, QtGui.QFont("Arial", 16)),
            ("Suprasegmental", IPASuprasegmental, QtGui.QFont("Arial", 16)),
        ]
        for title, ipa_cls, font in categories:
            ipa_box_layout.addWidget(self._generate_IPA_palette(title, ipa_cls, font))

        ipa_box = QtWidgets.QGroupBox("IPA Helpers")
        ipa_box.setLayout(ipa_box_layout)

        return ipa_box

    def _generate_IPA_palette(
        self, title: str, ipa_cls: type, font: QtGui.QFont | None = None, nb_columns: int = 8
    ) -> CollapsibleBox:
        """Generate a collapsible grid of clickable labels for the IPA characters of a given class"""
        box = CollapsibleBox(title)
        lay = QtWidgets.QGridLayout()

        ipa_chars: list[Any] = [cur_unicode for cur_unicode in IPA_CHARS if type(cur_unicode) is ipa_cls]
        for j, cur_unicode in enumerate(ipa_chars):
            label = QLabelClickable(str(cur_unicode))
            label.clicked.connect(self.onIPAInsert)
            if font is not None:
                label.setFont(font)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setToolTip(" ".join(cur_unicode.descriptors))
            lay.addWidget(label, j // nb_columns, j % nb_columns)

        box.setContentLayout(lay)
        return box

    def _load_annotation_file(self) -> None:
        """Ask for an annotation file and load it (errors are shown in a message box)"""
        if not self.confirmDiscardChanges():
            return

        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        annotation_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self._file_box, "Load annotation file", "", ANNOTATION_FILTERS, options=options
        )
        if not annotation_file:  # Cancelled
            return

        try:
            self.loadAnnotations(pathlib.Path(annotation_file))
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self._file_box, "Load annotation file", f"Cannot load the file:\n{ex}")

    def _save_annotation_file(self) -> bool:
        """Ask for a file name and save the annotations; the extension (or the selected filter) gives the format

        Returns
        -------
        bool
            True if the annotations have been saved
        """
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        annotation_file, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self._file_box, "Save annotation file", "", ANNOTATION_FILTERS, options=options
        )
        if not annotation_file:  # Cancelled
            return False

        # The extension decides the format; without a known extension, use the one of the selected filter
        annotation_file = pathlib.Path(annotation_file)
        try:
            serialiser = serialiser_for(annotation_file)
        except ValueError:
            extension, serialiser_cls = ANNOTATION_FORMATS.get(selected_filter, (".json", JSONSerialiser))
            annotation_file = annotation_file.with_name(annotation_file.name + extension)
            serialiser = serialiser_cls()

        dropped = serialiser.droppedTiers(self._model)
        if dropped:
            Button = QtWidgets.QMessageBox.StandardButton
            answer = QtWidgets.QMessageBox.question(
                self._file_box,
                "Save annotation file",
                f"This format holds one tier. These tiers will not be saved:\n{', '.join(dropped)}\n\nSave anyway?",
                Button.Save | Button.Cancel,
                Button.Cancel,
            )
            if answer != Button.Save:
                return False

        try:
            self._writeFile(serialiser, annotation_file)
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self._file_box, "Save annotation file", f"Cannot save the file:\n{ex}")
            return False
        if not dropped:  # NOTE: otherwise, closing must still warn about the tiers which are not in any file
            self._saved_contents = self._contents()
        self._wCurrentFile.setText(str(annotation_file.absolute()))
        return True

    def _writeFile(self, serialiser: AnnotationSerialiser, annotation_file: pathlib.Path) -> None:
        """Write the annotations in a temporary file which then replaces the file, so that a failure cannot damage it

        Parameters
        ----------
        serialiser : AnnotationSerialiser
            The serialiser of the format
        annotation_file : pathlib.Path
            The file
        """
        target = annotation_file.resolve()  # NOTE: a symbolic link must stay one
        temporary = target.with_name(target.name + ".tmp")
        try:
            serialiser.save(temporary, self._model)
            if target.exists():
                shutil.copymode(target, temporary)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def update_current_annotation(self, new_annotation: AnnotationItem | None = None) -> None:
        """Make an annotation the selected one (or clear the selection) and show it in the edition box

        This is the only place where the selection changes: the previous item is unselected and the new one
        selected (AnnotationItem.setSelectedState).

        Parameters
        ----------
        new_annotation : AnnotationItem, optional
            The item to select, None to clear the selection. (default: None)
        """
        if self._current_annotation is new_annotation:
            return

        self.commit()  # NOTE: a label typed without leaving its field ends here

        # If there is already a selected annotation => unselect it
        if self._current_annotation is not None:
            self._current_annotation.setSelectedState(False)
        self._current_annotation = new_annotation
        if self._current_annotation is not None:
            self._current_annotation.setSelectedState(True)

        # Update infobox base on the information of the new annotation
        if self._current_annotation is not None:
            self._wStartTime.setText(f"{self._current_annotation._segment.start_time:.4f}")
            self._wEndTime.setText(f"{self._current_annotation._segment.end_time:.4f}")
            self._wLabel.setText(self._current_annotation._segment.label)
            self._info_box.setVisible(True)
        else:
            self._wStartTime.setText("")
            self._wEndTime.setText("")
            self._wLabel.setText("")
            self._current_annotation = None
            self._info_box.setVisible(False)

    def onTimeEdited(self) -> None:
        """Apply the edited boundaries (once editing is finished), or restore the previous ones if they are invalid"""
        if self._current_annotation is None:
            return

        segment = self._current_annotation._segment
        try:
            start_time = float(self._wStartTime.text())
            end_time = float(self._wEndTime.text())
        except ValueError:
            start_time, end_time = -1.0, -1.0

        if 0 <= start_time < end_time:
            old_start, old_end = segment.start_time, segment.end_time
            self._current_annotation.setBounds(start_time, end_time)
            self._current_annotation.reportMoves(old_start, old_end)
            self.commit()
        else:
            self._wStartTime.setText(f"{segment.start_time:.4f}")
            self._wEndTime.setText(f"{segment.end_time:.4f}")

    def onLabelEdited(self) -> None:
        """Apply the edited label to the selected annotation"""
        if self._current_annotation is not None:
            self._current_annotation.updateLabel(self._wLabel.text())

    def onIPAInsert(self, ipa_symbol: str) -> None:
        """Insert an IPA symbol at the cursor position of the label field

        Parameters
        ----------
        ipa_symbol : str
            The symbol
        """
        self._wLabel.insert(ipa_symbol)
        self.commit()

    def updateTierList(self) -> None:
        """Fill the tier list from the model (hidden tiers are highlighted)"""
        self._list_tiers_widget.clear()
        for tier_name in self._model.annotations.keys():
            item = QListWidgetItemHideable(self._list_tiers_widget)
            item.setText(tier_name)
            if tier_name in self._model.ignored:
                item.toggleTierHidden()
            item.setLocked(tier_name in self._model.locked)
            self._list_tiers_widget.addItem(item)

    @property
    def model(self) -> AnnotationSet:
        """AnnotationSet: The annotations being edited"""
        return self._model

    @property
    def view(self) -> AnnotationDock | None:
        """AnnotationDock: The dock rendering the annotations (None until setView is called)"""
        return self._view

    def setAnnotationModel(self, annotation_model: AnnotationSet) -> None:
        """Replace the annotations being edited and redraw them

        Parameters
        ----------
        annotation_model : AnnotationSet
            The new annotations
        """
        self._model = annotation_model
        self._saved_contents = self._contents()
        self._undo_stack = [self._snapshot()]
        self._redo_stack = []
        self.historyChanged.emit()
        self.resetView()
        self.updateTierList()

    def loadAnnotations(self, annotation_file: pathlib.Path) -> None:
        """Load an annotation file (the format is given by its extension) and show it

        Parameters
        ----------
        annotation_file : pathlib.Path
            The file

        Raises
        ------
        ValueError
            if the format is unknown or the file is invalid
        """
        an_loader = serialiser_for(annotation_file)
        model = an_loader.load(annotation_file)
        self.setAnnotationModel(model)
        self._wCurrentFile.setText(str(annotation_file.absolute()))

    def resetView(self) -> None:
        """Redraw every tier from the model and notify the registered modules"""
        for module_handler in self.list_registered_modules:
            module_handler()
        if self._view is not None:
            self.update_current_annotation(None)  # The selected item is destroyed with its tier
            self._view.clear()
            self._view.setModel(self._model, self.update_current_annotation, self.commit)


#: The duration of an annotation added from the playhead, in seconds
DEFAULT_ANNOTATION_DURATION = 0.2

#: The number of operations which can be undone
MAX_UNDO_STEPS = 100

_controller: ControlLayout | None = None

# NOTE: kept outside of the controller so that registrations survive a re-creation of the controller
_registered_modules: set[Callable[[], None]] = set()


def get_controller() -> ControlLayout:
    """Return the annotation controller, creating it on first use (a QApplication must exist)

    The controller is also re-created if its Qt object has been deleted (e.g. when the window owning it was closed).
    """
    global _controller
    # NOTE: the layout wrapper can outlive the widgets it manages, so check one of them too
    if (_controller is None) or (not isQObjectAlive(_controller)) or (not isQObjectAlive(_controller._file_box)):
        _controller = ControlLayout(None)
    return _controller
