from pyqtgraph.Qt import QtWidgets, QtCore
from spiny.core import DataController


class SpectrumPraatController(DataController):
    def __init__(self, extractor, widget):
        self._name = "Spectrogram (Praat)"
        self._extractor = extractor
        self._widget = widget

    def setWavPlot(self, wav_plot):
        self._wav_plot = wav_plot

    def extract(self):
        self._extractor.extract()
        self.refresh()

    def setControlPanel(self, panel):
        groupBox = QtWidgets.QGroupBox("Spectrogram configuration")
        box = QtWidgets.QGridLayout()
        box.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        groupBox.setLayout(box)
        panel.addWidget(groupBox)
