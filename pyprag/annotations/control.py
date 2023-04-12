from pyqtgraph import QtCore, QtGui, QtWidgets
from ipapy import IPA_CHARS
from ipapy.ipachar import IPAConsonant, IPASuprasegmental, IPADiacritic, IPAVowel

from ..gui.widgets import CollapsibleBox

# from . import HTKAnnotation, TGTAnnotation


class QLabelClickable(QtWidgets.QLabel):
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
    def __init__(self, parent):
        super().__init__(parent)

        self._current_annotation = None
        # tier_box = self._generate_tier_box()
        # self._file_box = self._generate_file_box()
        self._info_box = self._generate_general_box()
        ipa_box = self._generate_IPA_box()

        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        # self.addWidget(self._file_box)
        # self.addWidget(tier_box)
        self.addWidget(self._info_box)
        self.addWidget(ipa_box)

        # Nothing selected => no info to show
        self._info_box.setVisible(False)

    def _generate_file_box(self):
        file_box_layout = QtWidgets.QGridLayout()
        file_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Start time
        l1 = QtWidgets.QLabel("Current File")
        self._wCurrentFile = QtWidgets.QLineEdit("none")
        self._wCurrentFile.setEnabled(False)
        file_box_layout.addWidget(l1, 1, 0)
        file_box_layout.addWidget(self._wCurrentFile, 1, 1)

        self._bSelectFile = QtWidgets.QPushButton("Select File")
        self._bSelectFile.clicked.connect(self._choose_annotation_file)
        self._bSelectFile.setDefault(False)
        self._bSelectFile.setAutoDefault(False)
        file_box_layout.addWidget(self._bSelectFile)

        file_box = QtWidgets.QGroupBox("Annotation File")
        file_box.setLayout(file_box_layout)

        return file_box

    def _generate_tier_box(self):
        tier_box = QtWidgets.QGroupBox("List of tiers")
        tier_box_layout = QtWidgets.QVBoxLayout()
        tier_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Start time
        listWidget = QtWidgets.QListWidget(tier_box)
        listWidget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        for i in range(5):
            item = QtWidgets.QListWidgetItem(listWidget)
            item.setText("Item {0}".format(i))
            listWidget.addItem(item)

        tier_box_layout.addWidget(listWidget)
        tier_box.setLayout(tier_box_layout)

        return tier_box

    def _generate_general_box(self):
        annotation_info_box_layout = QtWidgets.QGridLayout()
        annotation_info_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Start time
        l1 = QtWidgets.QLabel("Start Time (s)")
        self._wStartTime = QtWidgets.QLineEdit("<unknown>")
        self._wStartTime.setEnabled(False)
        annotation_info_box_layout.addWidget(l1, 1, 0)
        annotation_info_box_layout.addWidget(self._wStartTime, 1, 1)

        # End time
        l2 = QtWidgets.QLabel("End Time (s)")
        self._wEndTime = QtWidgets.QLineEdit("<unknown>")
        self._wEndTime.setEnabled(False)
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

        box = CollapsibleBox("Vowels")
        lay = QtWidgets.QGridLayout()

        # for cur_unicode in IPA_CHARS:
        #     print(type(cur_unicode))

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

    def _choose_annotation_file(self):
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        annotation_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self._file_box,
            "Load annotation file",
            "${HOME}",
            "TextGrid Files (*.TextGrid);; Label Files (*.lab)",
        )
        self._wCurrentFile.setText(annotation_file)

        # # Load annotation
        # annotation = None
        # if annotation_file != "":
        #     if annotation_file.endswith(".lab"):
        #         annotation = HTKAnnotation(annotation_file)
        #     elif annotation_file.endswith(".TextGrid"):
        #         annotation = TGTAnnotation(annotation_file)
        #     else:
        #         raise Exception("The annotation cannot be parsed, format is unknown")

    def update_current_annotation(self, new_annotation=None):
        if self._current_annotation == new_annotation:
            self._wStartTime.setText("<Unknown>")
            self._wEndTime.setText("<Unknown>")
            self._wLabel.setText("<Unkown>")
            self._current_annotation = None
            self._info_box.setVisible(False)
            return

        if self._current_annotation is not None:
            self._current_annotation.select()

        self._current_annotation = new_annotation

        if self._current_annotation is not None:
            self._wStartTime.setText(str(self._current_annotation._segment.start_time))
            self._wEndTime.setText(str(self._current_annotation._segment.end_time))
            self._wLabel.setText(self._current_annotation._segment.label)
            self._info_box.setVisible(True)

    def onLabelEdited(self):
        label = self._wLabel.text()
        if self._current_annotation is not None:
            self._current_annotation.updateLabel(label)

    def onIPAInsert(self, ipa_symbol):
        self._wLabel.insert(ipa_symbol)


controller = ControlLayout(None)
