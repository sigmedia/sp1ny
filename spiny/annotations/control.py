from __future__ import annotations

import pathlib
from collections.abc import Callable
from typing import Any

from ipapy import IPA_CHARS
from ipapy.ipachar import IPAConsonant, IPASuprasegmental, IPADiacritic, IPAVowel
from pyqtgraph import QtCore, QtGui, QtWidgets
from pyqtgraph.Qt import isQObjectAlive

from ..gui.widgets import CollapsibleBox
from .io import AnnotationSerialiser
from .model import AnnotationSet
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

    def toggleTierHidden(self) -> None:
        """Hide the tier if it is shown, show it if it is hidden"""
        self._hidden = not self._hidden

    def isTierHidden(self) -> bool:
        """Tell if the tier is hidden

        Returns
        -------
        bool
            True if the tier is hidden
        """
        return self._hidden


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

    UNSELECTED_COLOR = QtGui.QColor.fromRgb(234, 167, 153)
    DEFAULT_COLOR = QtGui.QColor.fromRgb(255, 255, 255)

    def __init__(self, parent: QtWidgets.QWidget | None) -> None:
        super().__init__(parent)

        # View and model
        self._model: AnnotationSet = AnnotationSet({}, set())
        self._view: AnnotationDock | None = None
        self._list_registered_modules = _registered_modules

        # Create the main layout
        box_layout = QtWidgets.QVBoxLayout()
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Prepare scrollbar
        scroll = QtWidgets.QScrollArea()
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
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
        self._list_tiers_widget = QtWidgets.QListWidget(tier_box)
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
                item.setBackground(QtGui.QBrush(ControlLayout.UNSELECTED_COLOR))
                self._model.ignored.add(item.text())
            else:
                item.setBackground(QtGui.QBrush(ControlLayout.DEFAULT_COLOR))
                self._model.ignored.discard(item.text())
            if self.view is not None:
                self.view.tiers_dict[item.text()].setVisible(not item.isTierHidden())

            item.setSelected(False)

    def _update_order(self) -> None:
        """Reorder the tiers of the model as in the list (after a drag and drop) and redraw them"""
        new_order = dict()
        for item_idx in range(self._list_tiers_widget.count()):
            item = self._list_tiers_widget.item(item_idx)
            new_order[item.text()] = self._model.annotations[item.text()]
            item.setSelected(False)

        self._model.annotations = new_order

        self.resetView()

    def _remove_tiers(self) -> None:
        """Remove the selected tiers from the model and the list, and redraw the tiers"""

        # Remove from the model
        list_index = []
        for item in self._list_tiers_widget.selectedItems():
            del self._model.annotations[item.text()]
            self._model.ignored.discard(item.text())
            list_index.append(self._list_tiers_widget.row(item))
        list_index.sort()

        while list_index:
            idx = list_index.pop()
            self._list_tiers_widget.takeItem(idx)

        self.resetView()

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
        item.setBackground(QtGui.QBrush(ControlLayout.DEFAULT_COLOR))
        self.resetView()
        self._list_tiers_widget.addItem(item)

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

        # setting background color to label when mouse hover over it
        hover_style = "QLabel:hover {{background-color: {}; color: white;}}".format(QtGui.QColor(134, 125, 125).name())

        ipa_chars: list[Any] = [cur_unicode for cur_unicode in IPA_CHARS if type(cur_unicode) is ipa_cls]
        for j, cur_unicode in enumerate(ipa_chars):
            label = QLabelClickable(str(cur_unicode))
            label.clicked.connect(self.onIPAInsert)
            if font is not None:
                label.setFont(font)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setToolTip(" ".join(cur_unicode.descriptors))
            label.setStyleSheet(hover_style)
            lay.addWidget(label, j // nb_columns, j % nb_columns)

        box.setContentLayout(lay)
        return box

    def _load_annotation_file(self) -> None:
        """Ask for an annotation file and load it (errors are shown in a message box)"""
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

    def _save_annotation_file(self) -> None:
        """Ask for a file name and save the annotations; the extension (or the selected filter) gives the format"""
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        annotation_file, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self._file_box, "Save annotation file", "", ANNOTATION_FILTERS, options=options
        )
        if not annotation_file:  # Cancelled
            return

        # The extension decides the format; without a known extension, use the one of the selected filter
        annotation_file = pathlib.Path(annotation_file)
        try:
            serialiser = serialiser_for(annotation_file)
        except ValueError:
            extension, serialiser_cls = ANNOTATION_FORMATS.get(selected_filter, (".json", JSONSerialiser))
            annotation_file = annotation_file.with_name(annotation_file.name + extension)
            serialiser = serialiser_cls()

        try:
            serialiser.save(annotation_file, self._model)
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self._file_box, "Save annotation file", f"Cannot save the file:\n{ex}")
            return
        self._wCurrentFile.setText(str(annotation_file.absolute()))

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
            self._current_annotation.setBounds(start_time, end_time)
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

    def updateTierList(self) -> None:
        """Fill the tier list from the model (hidden tiers are highlighted)"""
        self._list_tiers_widget.clear()
        for tier_name in self._model.annotations.keys():
            item = QListWidgetItemHideable(self._list_tiers_widget)
            item.setText(tier_name)
            if tier_name in self._model.ignored:
                item.toggleTierHidden()
                item.setBackground(QtGui.QBrush(ControlLayout.UNSELECTED_COLOR))
            else:
                item.setBackground(QtGui.QBrush(ControlLayout.DEFAULT_COLOR))
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
            self._view.clear()
            self._view.setModel(self._model, self.update_current_annotation)


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
