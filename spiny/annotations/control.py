from typing import Optional, Set
import pathlib
from pyqtgraph import QtCore, QtGui, QtWidgets
from ipapy import IPA_CHARS
from ipapy.ipachar import IPAConsonant, IPASuprasegmental, IPADiacritic, IPAVowel
from collections import OrderedDict

from ..gui.widgets import CollapsibleBox
from .model import AnnotationSet
from .visualisation import AnnotationDock
from .io.htk_lab import HTKLabelSerialiser
from .io.textgrid import TextGridSerialiser
from .io.json import JSONSerialiser

# from . import HTKAnnotation, TGTAnnotation


class QListWidgetItemHideable(QtWidgets.QListWidgetItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hidden = False

    def toggleHidden(self):
        self._hidden = not self._hidden

    def isHidden(self):
        return self._hidden


class QLabelClickable(QtWidgets.QLabel):
    """Clickable label used for IPA labels

    Source:
    https://stackoverflow.com/questions/74852195/pictures-in-pyqt5-gridlayout-look-stretched-when-window-is-maximized
    """

    clicked = QtCore.Signal(str)

    def __init__(self, parent=None):
        super(QLabelClickable, self).__init__(parent)

    def mousePressEvent(self, event):
        self.ultimo = "Clic"

    def mouseReleaseEvent(self, event):
        if self.ultimo == "Clic":
            QtCore.QTimer.singleShot(
                QtWidgets.QApplication.instance().doubleClickInterval(), self.performSingleClickAction
            )
        else:
            # Realizar acción de doble clic.
            self.clicked.emit(self.text())

    # def mouseDoubleClickEvent(self, event):
    #     self.ultimo = "Doble Clic"

    def performSingleClickAction(self):
        if self.ultimo == "Clic":
            self.clicked.emit(self.text())


class ControlLayout(QtWidgets.QVBoxLayout):

    UNSELECTED_COLOR = QtGui.QColor.fromRgb(234, 167, 153)
    DEFAULT_COLOR = QtGui.QColor.fromRgb(255, 255, 255)

    def __init__(self, parent):
        super().__init__(parent)

        # View and model
        self._model: AnnotationSet = AnnotationSet({}, set())
        self._view: Optional[AnnotationDock] = None
        self._list_registered_modules = set()

        # Create the main layout
        box_layout = QtWidgets.QVBoxLayout()
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Prepare scrollbar
        scroll = QtWidgets.QScrollArea()
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)

        # Generate the necessary widgets
        self._current_annotation = None
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
    def list_registered_modules(self) -> Set:
        return self._list_registered_modules

    def setView(self, annotation_dock: AnnotationDock) -> None:
        self._view = annotation_dock

    def _generate_file_box(self):
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

    def _generate_tier_box(self):
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
        self._list_tiers_widget.itemSelectionChanged.connect(self._tiers_list_updated)

        return tier_box

    def _toggle_tier(self):
        # Remove from the model
        for idx, item in enumerate(self._list_tiers_widget.selectedItems()):
            item.toggleHidden()
            if item.isHidden():
                item.setBackground(QtGui.QBrush(ControlLayout.UNSELECTED_COLOR))
                self._model.ignored.add(item.text())
                self.view.tiers_dict[item.text()].plotItem.setVisible(False)
            else:
                item.setBackground(QtGui.QBrush(ControlLayout.DEFAULT_COLOR))
                self._model.ignored.remove(item.text())
                self.view.tiers_dict[item.text()].plotItem.setVisible(True)

            item.setSelected(False)

    def _update_order(self):
        new_order = OrderedDict()
        for item_idx in range(self._list_tiers_widget.count()):
            item = self._list_tiers_widget.item(item_idx)
            new_order[item.text()] = self._model.annotations[item.text()]
            item.setSelected(False)

        self._model.annotations = new_order

        self.resetView()

    def _remove_tiers(self):

        # Remove from the model
        list_index = []
        for item in self._list_tiers_widget.selectedItems():
            print("===========")
            print(item.text())
            del self._model.annotations[item.text()]
            list_index.append(self._list_tiers_widget.row(item))

        while list_index:
            idx = list_index.pop()
            self._list_tiers_widget.takeItem(idx)

        self.resetView()

    def _add_tier(self):
        tier_name, ok = QtWidgets.QInputDialog.getText(self._tier_box, "New tier", "Enter the name of the tier:")

        if ok:
            self._model.annotations[tier_name] = []
            item = QListWidgetItemHideable(self._list_tiers_widget)
            item.setText(tier_name)
            item.setBackground(QtGui.QBrush(ControlLayout.DEFAULT_COLOR))
            self.resetView()
            self._list_tiers_widget.addItem(item)

    # TODO: this is hardcore for nothing
    #       needs to just find the item which changed instead of going through everything
    def _tiers_list_updated(self, *arg):
        if self._view is None:
            return

        for i_item in range(self._list_tiers_widget.count()):
            item = self._list_tiers_widget.item(i_item)
            cur_name = item.text()
            self._view._tiers_dict[cur_name].setVisible(True)

    def _generate_general_box(self):
        annotation_info_box_layout = QtWidgets.QGridLayout()
        annotation_info_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Start time
        l1 = QtWidgets.QLabel("Start Time (s)")
        self._wStartTime = QtWidgets.QLineEdit("-1")
        # self._wStartTime.setEnabled(False)
        self._wStartTime.textEdited.connect(self.onTimeEdited)
        annotation_info_box_layout.addWidget(l1, 1, 0)
        annotation_info_box_layout.addWidget(self._wStartTime, 1, 1)

        # End time
        l2 = QtWidgets.QLabel("End Time (s)")
        self._wEndTime = QtWidgets.QLineEdit("-1")
        # self._wEndTime.setEnabled(False)
        self._wEndTime.textEdited.connect(self.onTimeEdited)
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

    def _generate_IPA_box(self):

        ipa_box_layout = QtWidgets.QVBoxLayout()
        ipa_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # ###
        # # Add consonnants
        # ################################################################
        box = CollapsibleBox("Consonnants")
        lay = QtWidgets.QGridLayout()

        for j, cur_unicode in enumerate(IPA_CHARS):
            if type(cur_unicode) == IPAConsonant:
                label = QLabelClickable("{}".format(cur_unicode))
                label.clicked.connect(self.onIPAInsert)
                label.setAlignment(QtCore.Qt.AlignCenter)
                label.setToolTip(" ".join(cur_unicode.descriptors))

                # setting background color to label when mouse hover over it
                color = QtGui.QColor(134, 125, 125)
                label.setStyleSheet("QLabel:hover {{background-color: {}; color: white;}}".format(color.name()))
                lay.addWidget(label, j // 8, j % 8)

        box.setContentLayout(lay)
        ipa_box_layout.addWidget(box)

        # ###
        # # Add vowels
        # ################################################################
        box = CollapsibleBox("Vowels")
        lay = QtWidgets.QGridLayout()

        j = -1
        for cur_unicode in IPA_CHARS:
            if type(cur_unicode) == IPAVowel:
                j += 1
                label = QLabelClickable("{}".format(cur_unicode))
                label.clicked.connect(self.onIPAInsert)
                label.setAlignment(QtCore.Qt.AlignCenter)
                label.setToolTip(" ".join(cur_unicode.descriptors))

                # setting background color to label when mouse hover over it
                color = QtGui.QColor(134, 125, 125)
                label.setStyleSheet("QLabel:hover {{background-color: {}; color: white;}}".format(color.name()))
                lay.addWidget(label, j // 8, j % 8)

        box.setContentLayout(lay)
        ipa_box_layout.addWidget(box)

        # ###
        # # Add diacritics
        # ################################################################
        box = CollapsibleBox("Diacritics")
        lay = QtWidgets.QGridLayout()

        j = -1
        for cur_unicode in IPA_CHARS:
            if type(cur_unicode) == IPADiacritic:
                j += 1
                label = QLabelClickable("{}".format(cur_unicode))
                label.clicked.connect(self.onIPAInsert)
                label.setFont(QtGui.QFont("Arial", 16))
                label.setAlignment(QtCore.Qt.AlignCenter)
                label.setToolTip(" ".join(cur_unicode.descriptors))

                # setting background color to label when mouse hover over it
                color = QtGui.QColor(134, 125, 125)
                label.setStyleSheet("QLabel:hover {{background-color: {}; color: white;}}".format(color.name()))
                lay.addWidget(label, j // 8, j % 8)

        box.setContentLayout(lay)
        ipa_box_layout.addWidget(box)

        # ###
        # # Add supra-segmental markers
        # ################################################################
        box = CollapsibleBox("Suprasegmental")
        lay = QtWidgets.QGridLayout()

        j = -1
        for cur_unicode in IPA_CHARS:
            if type(cur_unicode) == IPASuprasegmental:
                j += 1
                label = QLabelClickable("{}".format(cur_unicode))
                label.clicked.connect(self.onIPAInsert)
                label.setFont(QtGui.QFont("Arial", 16))
                label.setAlignment(QtCore.Qt.AlignCenter)
                label.setToolTip(" ".join(cur_unicode.descriptors))

                # setting background color to label when mouse hover over it
                color = QtGui.QColor(134, 125, 125)
                label.setStyleSheet("QLabel:hover {{background-color: {}; color: white;}}".format(color.name()))
                lay.addWidget(label, j // 8, j % 8)

        box.setContentLayout(lay)
        ipa_box_layout.addWidget(box)

        ipa_box = QtWidgets.QGroupBox("IPA Helpers")

        ipa_box.setLayout(ipa_box_layout)

        return ipa_box

    def _load_annotation_file(self):
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        annotation_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self._file_box,
            "Load annotation file",
            "",
            "TextGrid Files (*.TextGrid);;HTK Label Files (*.lab);;JSON Files (*.json)",
        )
        self._wCurrentFile.setText(annotation_file)
        self.loadAnnotations(pathlib.Path(annotation_file))

    def _save_annotation_file(self):
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        annotation_file, _ = QtWidgets.QFileDialog.getSaveFileName(
            self._file_box,
            "Save annotation file",
            "",
            "TextGrid Files (*.TextGrid);;HTK Label Files (*.lab);;JSON Files (*.json)",
        )
        an_loader = JSONSerialiser()
        self._wCurrentFile.setText(annotation_file)
        an_loader.save(annotation_file, self._model)

    def update_current_annotation(self, new_annotation=None):
        if self._current_annotation == new_annotation:
            return

        # If there is already a selected annotation => unselect it
        if self._current_annotation is not None:
            self._current_annotation.select()
        self._current_annotation = new_annotation

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

    def onTimeEdited(self):
        if self._current_annotation is not None:
            self._current_annotation.setBounds(float(self._wStartTime.text()), float(self._wEndTime.text()))

    def onLabelEdited(self):
        if self._current_annotation is not None:
            self._current_annotation.updateLabel(self._wLabel.text())

    def onIPAInsert(self, ipa_symbol):
        self._wLabel.insert(ipa_symbol)

    def updateTierList(self):
        self._list_tiers_widget.clear()
        for tier_name in self._model.annotations.keys():
            item = QListWidgetItemHideable(self._list_tiers_widget)
            item.setText(tier_name)
            self._list_tiers_widget.addItem(item)

    @property
    def model(self):
        return self._model

    @property
    def view(self):
        return self._view

    def setAnnotationModel(self, annotation_model: AnnotationSet) -> None:
        self._model = annotation_model
        self.resetView()
        self.updateTierList()

    def loadAnnotations(self, annotation_file: pathlib.Path) -> None:

        if annotation_file.name.endswith(".lab"):
            an_loader = HTKLabelSerialiser()
        elif annotation_file.name.endswith(".TextGrid"):
            an_loader = TextGridSerialiser()
        elif annotation_file.name.endswith(".json"):
            an_loader = JSONSerialiser()
        else:
            raise Exception("The annotation cannot be parsed, format is unknown")
        model = an_loader.load(annotation_file)
        self.setAnnotationModel(model)
        self._wCurrentFile.setText(str(annotation_file.absolute()))

    def resetView(self):
        for module_handler in self.list_registered_modules:
            module_handler()
        if self._view is not None:
            self._view.clear()
            self._view.setModel(self._model, self.update_current_annotation)


controller = ControlLayout(None)
