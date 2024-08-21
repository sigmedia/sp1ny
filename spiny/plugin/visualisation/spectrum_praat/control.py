from pyqtgraph.Qt import QtWidgets, QtCore
from spiny.visualisation import DataController


class SpectrumPraatController(DataController):
    def __init__(self, extractor, widget):
        super().__init__("Spectrogram (Praat)", extractor, widget)

    def setControlPanel(self, panel):
        groupBox = QtWidgets.QGroupBox("Spectrogram configuration")
        box = QtWidgets.QGridLayout()
        box.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        groupBox.setLayout(box)
        panel.addWidget(groupBox)
