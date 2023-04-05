from pyqtgraph.Qt import QtWidgets, QtCore
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
        self._extractor._threshold_amp = (int(self._wMinAmp.text()), int(self._wMaxAmp.text()))
        self._extractor.extract()
        self.refresh()

    def setControlPanel(self, panel):
        # Create group box widget and initialize the main layout
        groupBox = QtWidgets.QGroupBox("Spectrogram configuration")
        box = QtWidgets.QGridLayout()
        box.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Frequency widgets
        l1 = QtWidgets.QLabel("Min Freq.")
        self._wMinFreq = QtWidgets.QLineEdit("0")
        l2 = QtWidgets.QLabel("Max Freq.")
        self._wMaxFreq = QtWidgets.QLineEdit("5000")
        box.addWidget(l1, 0, 0)
        box.addWidget(l2, 1, 0)
        box.addWidget(self._wMinFreq, 0, 1)
        box.addWidget(self._wMaxFreq, 1, 1)

        # Frequency widgets
        l1 = QtWidgets.QLabel("Min Amp.")
        self._wMinAmp = QtWidgets.QLineEdit("-70")
        l2 = QtWidgets.QLabel("Max Amp.")
        self._wMaxAmp = QtWidgets.QLineEdit("0")
        box.addWidget(l1, 2, 0)
        box.addWidget(l2, 3, 0)
        box.addWidget(self._wMinAmp, 2, 1)
        box.addWidget(self._wMaxAmp, 3, 1)

        # Don't forget to add the extract button
        bExtract = QtWidgets.QPushButton("Extract")
        bExtract.clicked.connect(self.extract)
        bExtract.setDefault(False)
        bExtract.setAutoDefault(False)
        box.addWidget(bExtract)

        groupBox.setLayout(box)
        panel.addWidget(groupBox)
