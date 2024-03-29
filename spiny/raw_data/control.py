from pyqtgraph.Qt import QtWidgets
from spiny.core import DataController


class RawDataController(DataController):
    def __init__(self, extractor, widget):
        self._name = "Raw DATA"
        self._extractor = extractor
        self._widget = widget

    def setWavPlot(self, wav_plot):
        self._wav_plot = wav_plot

    def loadCoefficientFile(self, coefficient_file, dimension, frameshift):
        self._extractor.loadCoefficientFile(coefficient_file, dimension, frameshift)

    def extract(self):
        self._extractor.extract()
        self.refresh()

    def setControlPanel(self, panel):
        panel.addWidget(QtWidgets.QWidget())
