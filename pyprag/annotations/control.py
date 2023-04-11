from pyqtgraph import QtCore, QtGui, QtWidgets
from ipapy import IPA_CHARS
from ipapy.ipachar import IPAConsonant, IPASuprasegmental, IPADiacritic, IPAVowel

# from . import HTKAnnotation, TGTAnnotation


class CollapsibleBox(QtWidgets.QWidget):
    """This class has been adapted from a PyQt5 example

    The exampple is provided at this address: https://stackoverflow.com/a/52617714
    """

    def __init__(self, title="", parent=None):
        super(CollapsibleBox, self).__init__(parent)

        self.toggle_button = QtWidgets.QToolButton(text=title, checkable=True, checked=False)
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(QtCore.Qt.RightArrow)
        self.toggle_button.pressed.connect(self.on_pressed)

        self.toggle_animation = QtCore.QParallelAnimationGroup(self)

        self.content_area = QtWidgets.QScrollArea(maximumHeight=0, minimumHeight=0)
        self.content_area.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.content_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

        self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self, b"minimumHeight"))
        self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self, b"maximumHeight"))
        self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self.content_area, b"maximumHeight"))

    # @QtCore.pyqtSlot()
    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(QtCore.Qt.DownArrow if not checked else QtCore.Qt.RightArrow)
        self.toggle_animation.setDirection(
            QtCore.QAbstractAnimation.Forward if not checked else QtCore.QAbstractAnimation.Backward
        )
        self.toggle_animation.start()

    def setContentLayout(self, layout):
        lay = self.content_area.layout()
        del lay
        self.content_area.setLayout(layout)
        collapsed_height = self.sizeHint().height() - self.content_area.maximumHeight()
        content_height = layout.sizeHint().height()
        for i in range(self.toggle_animation.animationCount()):
            animation = self.toggle_animation.animationAt(i)
            animation.setDuration(500)
            animation.setStartValue(collapsed_height)
            animation.setEndValue(collapsed_height + content_height)

        content_animation = self.toggle_animation.animationAt(self.toggle_animation.animationCount() - 1)
        content_animation.setDuration(500)
        content_animation.setStartValue(0)
        content_animation.setEndValue(content_height)


class ControlLayout(QtWidgets.QVBoxLayout):
    def __init__(self, parent):
        super().__init__(parent)

        self._file_box = self._generate_file_box()
        info_box = self._generate_general_box()
        ipa_box = self._generate_IPA_box()

        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.addWidget(self._file_box)
        self.addWidget(info_box)
        self.addWidget(ipa_box)

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
        annotation_info_box_layout.addWidget(l3, 3, 0)
        annotation_info_box_layout.addWidget(self._wLabel, 3, 1)

        annotation_info_box = QtWidgets.QGroupBox("Current Annotation")
        annotation_info_box.setLayout(annotation_info_box_layout)

        return annotation_info_box

    def _generate_IPA_box(self):

        ipa_box_layout = QtWidgets.QVBoxLayout()
        ipa_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        box = CollapsibleBox("Pulmonic Consonnants")
        lay = QtWidgets.QGridLayout()

        for j, cur_unicode in enumerate(IPA_CHARS):
            if type(cur_unicode) == IPAConsonant:
                label = QtWidgets.QLabel("{}".format(cur_unicode))
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
                label = QtWidgets.QLabel("{}".format(cur_unicode))
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
                label = QtWidgets.QLabel("{}".format(cur_unicode))
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
                label = QtWidgets.QLabel("{}".format(cur_unicode))
                label.setAlignment(QtCore.Qt.AlignCenter)
                label.setToolTip(" ".join(cur_unicode.descriptors))

                # setting background color to label when mouse hover over it
                color = QtGui.QColor(134, 125, 125)
                label.setStyleSheet("QLabel:hover {{background-color: {}; color: white;}}".format(color.name()))
                lay.addWidget(label, j // 8, j % 8)

        box.setContentLayout(lay)
        ipa_box_layout.addWidget(box)

        ipa_box = QtWidgets.QGroupBox("IPA Helpers")

        # self.scroll = QtWidgets.QScrollArea()
        # self.widget = QtWidgets.QWidget()
        # self.vbox = QtWidgets.QVBoxLayout()
        # self.widget.setLayout(self.vbox)
        # self.addWidget(self.scroll)

        # self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        # self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        # self.scroll.setWidgetResizable(True)
        # self.scroll.setWidget(self.widget)

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
