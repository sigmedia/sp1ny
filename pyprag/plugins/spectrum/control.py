from pyqtgraph.Qt import QtWidgets
from pyprag.core import DataController


class SpectrumController(DataController):
    def __init__(self, extractor, widget):
        self._name = "Spectrogram"
        self._extractor = extractor
        self._widget = widget

    def setWav(self, wav, sampling_rate, wav_plot):
        assert wav is not None
        self._extractor.setWav(wav, sampling_rate)
        self._wav_plot = wav_plot

    def extract(self):
        self._extractor._cutoff = (int(self._wMinFreq.text()), int(self._wMaxFreq.text()))
        self._extractor.extract()
        self.refresh()

    def addLayoutToPanel(self, panel):
        groupBox = QtWidgets.QGroupBox("Spectrogram configuration")

        # F0 widgets
        l1 = QtWidgets.QLabel("Min Freq.")
        self._wMinFreq = QtWidgets.QLineEdit("0")

        # Energy widgets
        l2 = QtWidgets.QLabel("Max Freq.")
        self._wMaxFreq = QtWidgets.QLineEdit("5000")

        # Setup the contr
        box = QtWidgets.QGridLayout()
        box.addWidget(l1, 0, 0)
        box.addWidget(l2, 1, 0)
        box.addWidget(self._wMinFreq, 0, 1)
        box.addWidget(self._wMaxFreq, 1, 1)
        groupBox.setLayout(box)

        # Don't forget to add the extract button
        bExtract = QtWidgets.QPushButton("Extract")
        bExtract.clicked.connect(self.extract)
        bExtract.setDefault(False)
        bExtract.setAutoDefault(False)

        control_layout = QtWidgets.QVBoxLayout()
        control_layout.addWidget(groupBox)
        control_layout.addWidget(bExtract)
        panel.addLayout(control_layout)
