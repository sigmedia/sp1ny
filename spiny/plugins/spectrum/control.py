from pyqtgraph.Qt import QtWidgets, QtCore
from spiny.core import DataController


class SpectrumController(DataController):
    def __init__(self, extractor, widget):
        self._name = "Spectrogram"
        self._extractor = extractor
        self._widget = widget

    def setWavPlot(self, wav_plot):
        self._wav_plot = wav_plot

    def extract(self):
        self._extractor._cutoff = (self._wMinFreq.value(), self._wMaxFreq.value())
        self._extractor._threshold_amp = (self._wMinAmp.value(), self._wMaxAmp.value())
        self._extractor._frameshift = self._wFrameshift.value()
        self._extractor._framelength = self._wFramelength.value()
        self._extractor._fft_length = self._wFFTLength.value()
        self._extractor._window = self._wWindow.currentText()
        try:
            self._extractor.extract()
        except ValueError as ex:  # Inconsistent parameters (or unknown window)
            QtWidgets.QMessageBox.warning(None, "Spectrogram configuration", str(ex))
            return
        self.refresh()

    @staticmethod
    def _spinBox(minimum, maximum, value, suffix=""):
        box = QtWidgets.QSpinBox()
        box.setRange(minimum, maximum)
        box.setValue(value)
        box.setSuffix(suffix)
        return box

    def setControlPanel(self, panel):

        # Refresh
        refresh_box_layout = QtWidgets.QGridLayout()
        refresh_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        l1 = QtWidgets.QLabel("Min Freq.")
        self._wMinFreq = self._spinBox(0, 96000, 0, " Hz")
        l2 = QtWidgets.QLabel("Max Freq.")
        self._wMaxFreq = self._spinBox(1, 96000, 5000, " Hz")
        refresh_box_layout.addWidget(l1, 0, 0)
        refresh_box_layout.addWidget(l2, 1, 0)
        refresh_box_layout.addWidget(self._wMinFreq, 0, 1)
        refresh_box_layout.addWidget(self._wMaxFreq, 1, 1)

        # Amplitude widgets
        l1 = QtWidgets.QLabel("Min Amp.")
        self._wMinAmp = self._spinBox(-200, 0, -70, " dB")
        l2 = QtWidgets.QLabel("Max Amp.")
        self._wMaxAmp = self._spinBox(-200, 0, 0, " dB")
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
        self._wFFTLength = self._spinBox(16, 65536, 2048)
        extract_box_layout.addWidget(l1, 4, 0)
        extract_box_layout.addWidget(self._wFFTLength, 4, 1)

        l1 = QtWidgets.QLabel("Frame shift (ms)")
        self._wFrameshift = self._spinBox(1, 1000, 5)
        extract_box_layout.addWidget(l1, 5, 0)
        extract_box_layout.addWidget(self._wFrameshift, 5, 1)

        l1 = QtWidgets.QLabel("Frame length (ms)")
        self._wFramelength = self._spinBox(1, 1000, 30)
        extract_box_layout.addWidget(l1, 6, 0)
        extract_box_layout.addWidget(self._wFramelength, 6, 1)

        l1 = QtWidgets.QLabel("Window")
        self._wWindow = QtWidgets.QComboBox()
        self._wWindow.setEditable(True)  # any scipy.signal.get_window name is accepted
        self._wWindow.addItems(["hamming", "hann", "blackman", "blackmanharris", "boxcar"])
        extract_box_layout.addWidget(l1, 7, 0)
        extract_box_layout.addWidget(self._wWindow, 7, 1)

        extract_box = QtWidgets.QGroupBox("Extraction parameters")
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
