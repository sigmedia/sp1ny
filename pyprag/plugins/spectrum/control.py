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
        self._extractor._frameshift = int(self._wFrameshift.text())
        self._extractor._framelength = int(self._wFramelength.text())
        self._extractor._fft_length = int(self._wFFTLength.text())
        self._extractor._window = self._wWindow.text()
        self._extractor.extract()
        self.refresh()

    def setControlPanel(self, panel):

        # Refresh
        refresh_box_layout = QtWidgets.QGridLayout()
        refresh_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        l1 = QtWidgets.QLabel("Min Freq.")
        self._wMinFreq = QtWidgets.QLineEdit("0")
        l2 = QtWidgets.QLabel("Max Freq.")
        self._wMaxFreq = QtWidgets.QLineEdit("5000")
        refresh_box_layout.addWidget(l1, 0, 0)
        refresh_box_layout.addWidget(l2, 1, 0)
        refresh_box_layout.addWidget(self._wMinFreq, 0, 1)
        refresh_box_layout.addWidget(self._wMaxFreq, 1, 1)

        # Amplitude widgets
        l1 = QtWidgets.QLabel("Min Amp.")
        self._wMinAmp = QtWidgets.QLineEdit("-70")
        l2 = QtWidgets.QLabel("Max Amp.")
        self._wMaxAmp = QtWidgets.QLineEdit("0")
        refresh_box_layout.addWidget(l1, 2, 0)
        refresh_box_layout.addWidget(l2, 3, 0)
        refresh_box_layout.addWidget(self._wMinAmp, 2, 1)
        refresh_box_layout.addWidget(self._wMaxAmp, 3, 1)

        refresh_box = QtWidgets.QGroupBox("Refresh parameters")
        refresh_box.setLayout(refresh_box_layout)

        # Extraction parameters
        extract_box_layout = QtWidgets.QGridLayout()
        extract_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        l1 = QtWidgets.QLabel("FFT Length")
        self._wFFTLength = QtWidgets.QLineEdit("2048")
        extract_box_layout.addWidget(l1, 4, 0)
        extract_box_layout.addWidget(self._wFFTLength, 4, 1)

        l1 = QtWidgets.QLabel("Frame shift (ms)")
        self._wFrameshift = QtWidgets.QLineEdit("5")
        extract_box_layout.addWidget(l1, 5, 0)
        extract_box_layout.addWidget(self._wFrameshift, 5, 1)

        l1 = QtWidgets.QLabel("Frame length (ms)")
        self._wFramelength = QtWidgets.QLineEdit("5")
        extract_box_layout.addWidget(l1, 6, 0)
        extract_box_layout.addWidget(self._wFramelength, 6, 1)

        l1 = QtWidgets.QLabel("Window")
        self._wWindow = QtWidgets.QLineEdit("hamming")
        extract_box_layout.addWidget(l1, 7, 0)
        extract_box_layout.addWidget(self._wWindow, 7, 1)

        extract_box = QtWidgets.QGroupBox("Refresh parameters")
        extract_box.setLayout(extract_box_layout)

        main_group_box = QtWidgets.QGroupBox("Spectrogram configuration")
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(refresh_box)
        main_layout.addWidget(extract_box)

        # Don't forget to add the extract button
        # TODO: for now everything needs to be extracted
        bExtract = QtWidgets.QPushButton("Extract")
        bExtract.clicked.connect(self.extract)
        bExtract.setDefault(False)
        bExtract.setAutoDefault(False)
        main_layout.addWidget(bExtract)

        main_group_box.setLayout(main_layout)
        panel.addWidget(main_group_box)
