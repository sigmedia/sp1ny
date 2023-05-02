from pyqtgraph.Qt import QtWidgets, QtCore
from spiny.core import DataController


class WaveletController(DataController):
    def __init__(self, extractor, widget):
        self._name = "Wavelet"
        self._extractor = extractor
        self._widget = widget

    def setWavPlot(self, wav_plot):
        self._wav_plot = wav_plot

    def extract(self):
        self._extractor.extract()
        self.refresh()

    def setControlPanel(self, panel):

        # Create the groupbox
        groupBox = QtWidgets.QGroupBox("Wavelet configuration")

        # Create the main layout
        box_layout = QtWidgets.QVBoxLayout()
        box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Add different feature group part
        box_layout.addWidget(self.setF0Limits())
        box_layout.addWidget(self.prosodicFeats())
        box_layout.addWidget(self.featureCombination())
        # box_layout.addWidget(self.weight())
        box_layout.addWidget(self.signalTiers())
        box_layout.addWidget(self.createTierList())

        # Fnalize and add the widget to the panel
        groupBox.setLayout(box_layout)
        panel.addWidget(groupBox)

    def setF0Limits(self):
        """Setup the F0 limits area

        Parameters
        ----------
        self: SigWindow
            The current window object

        Returns
        -------
        groupBox: QGroupBox
            The groupbox containing all the controls needed for F0 limit definition
        """

        # Min F0
        self.min_f0 = QtWidgets.QLineEdit("min F0")
        self.min_f0.setText("50.0")  # str(self.configuration["f0"]["min_f0"]))
        self.min_f0.setInputMask("000")
        # self.min_f0.textChanged.connect(self.onF0Changed)

        # Max F0
        self.max_f0 = QtWidgets.QLineEdit("max F0")
        self.max_f0.setText("400.0")  # str(self.configuration["f0"]["max_f0"]))
        self.max_f0.setInputMask("000")
        # self.max_f0.textChanged.connect(self.onF0Changed)

        # Voicing
        self.voicing = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.voicing.setSliderPosition(50)  # self.configuration["f0"]["voicing_threshold"])
        # self.voicing.valueChanged.connect(self.onF0Changed)

        # Harmonics
        self.harmonics = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.harmonics.setSliderPosition(50)
        self.harmonics.setVisible(False)
        # self.harmonics.valueChanged.connect(self.onF0Changed)

        # Setup groupbox
        hbox = QtWidgets.QVBoxLayout()
        hbox.addWidget(self.min_f0)
        hbox.addWidget(self.max_f0)
        hbox.addWidget(self.voicing)
        # hbox.addWidget(self.harmonics)

        groupBox = QtWidgets.QGroupBox("minF0, maxF0, voicing threshold")  # , harmonics")
        # groupBox.setMaximumSize(200,200)
        groupBox.setLayout(hbox)
        groupBox.setToolTip("min and max Hz of the speaker's f0 range, voicing threshold")

        return groupBox

    def prosodicFeats(self):
        """Function to setup the feature weights for the CWT

        Parameters
        ----------
        self: SigWindowtype
            The current window object

        Returns
        -------
        groupBox: QGroupBox
            The groupbox containing all the controls related to the feature weights

        """
        groupBox = QtWidgets.QGroupBox("Feature Weights for CWT")

        # F0 widgets
        l1 = QtWidgets.QLabel("F0")
        self.wF0 = QtWidgets.QLineEdit("1.0")  # str(self.configuration["feature_combination"]["weights"]["f0"]))
        self.wF0.setInputMask("0.0")
        self.wF0.setMaxLength(3)

        # Energy widgets
        l2 = QtWidgets.QLabel("Energy")
        self.wEnergy = QtWidgets.QLineEdit(
            "1.0"
        )  # str(self.configuration["feature_combination"]["weights"]["energy"]))
        self.wEnergy.setInputMask("0.0")
        self.wEnergy.setMaxLength(3)

        # Duration widgets
        l3 = QtWidgets.QLabel("Duration")
        self.wDuration = QtWidgets.QLineEdit(
            "0.0"
        )  # str(self.configuration["feature_combination"]["weights"]["duration"]))
        self.wDuration.setInputMask("0.0")
        self.wDuration.setMaxLength(3)

        # Setup the groupbox
        box = QtWidgets.QGridLayout()
        box.addWidget(l1, 0, 0)
        box.addWidget(l2, 0, 1)
        box.addWidget(l3, 0, 2)
        box.addWidget(self.wF0, 1, 0)
        box.addWidget(self.wEnergy, 1, 1)
        box.addWidget(self.wDuration, 1, 2)
        groupBox.setLayout(box)

        return groupBox

    def signalTiers(self):
        """?

        Parameters
        ----------
        self: SigWindowtype
            The current window object

        Returns
        -------
        groupBox: QGroupBox
            The groupbox containing all the controls related to the feature weights

        """

        # Signal tier
        self.signalTiers = QtWidgets.QListWidget()
        self.signalTiers.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        # NOTE: self.signalTiers.clicked.connect(self.onSignalRate)

        # Signal rate
        self.signalRate = QtWidgets.QCheckBox("Estimate speech rate from signal")
        # NOTE: self.signalRate.setChecked(self.configuration["duration"]["acoustic_estimation"])
        # NOTE: self.signalRate.clicked.connect(self.onSignalRate)

        # Delta
        self.diffDur = QtWidgets.QCheckBox("Use delta-duration")
        self.diffDur.setToolTip(
            "Point-wise difference of the durations signal, "
            + "empirically found to improve boundary detection in some cases"
        )
        # NOTE: self.diffDur.setChecked(self.configuration["duration"]["delta_duration"])
        # NOTE: self.diffDur.clicked.connect(self.onSignalRate)

        # Zero duration signal at unit boundaries
        self.bump = QtWidgets.QCheckBox("Emphasize differences")
        self.bump.setToolTip("duration signal with valleys relative to adjacent unit duration differences")
        # NOTE: self.bump.setChecked(self.configuration["duration"]["bump"])
        # NOTE: self.bump.clicked.connect(self.onSignalRate)

        # Setup the group box
        box = QtWidgets.QVBoxLayout()
        box.addWidget(self.signalTiers)
        box.addWidget(self.diffDur)
        box.addWidget(self.signalRate)
        box.addWidget(self.bump)
        groupBox = QtWidgets.QGroupBox("Tier(s) for Duration Signal")
        # groupBox.setMaximumSize(400, 150)  # FIXME: see for not having hardcoded size
        groupBox.setLayout(box)
        groupBox.setToolTip(
            "Generate duration signal from a tier or as a sum of two or more tiers.\n"
            + "Shift-click to multi-select, Ctrl-click to de-select"
        )

        return groupBox

    def createTierList(self):
        groupBox = QtWidgets.QGroupBox("Tier for Prosody Annotation")
        self.tierlist = QtWidgets.QComboBox()
        # NOTE: self.tierlist.activated.connect(self.onTierChanged)
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.tierlist)
        groupBox.setLayout(vbox)
        return groupBox

    def weight(self):
        groupBox = QtWidgets.QGroupBox("frequency / time resolution")
        groupBox.setToolTip(
            "Interpolation between Mexican Hat wavelet (left) and Gaussian filter / scale-space (right)."
        )
        self.weight = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.weight.sliderReleased.connect(self.onWeightChanged)

        hbox = QtWidgets.QVBoxLayout()
        hbox.addWidget(self.weight)
        groupBox.setLayout(hbox)
        groupBox.setVisible(False)
        return groupBox

    def featureCombination(self):

        groupBox = QtWidgets.QGroupBox("Feature Combination Method")

        combination_method = QtWidgets.QButtonGroup()  # Number group

        self.sum_feats = QtWidgets.QRadioButton("sum")
        self.mul_feats = QtWidgets.QRadioButton("product")
        self.mul_feats.setChecked(True)

        combination_method.addButton(self.sum_feats)
        combination_method.addButton(self.mul_feats)

        # self.sum_feats.clicked.connect(self.onSignalRate)
        # self.mul_feats.clicked.connect(self.onSignalRate)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.sum_feats)
        hbox.addWidget(self.mul_feats)
        groupBox.setLayout(hbox)
        groupBox.setVisible(True)

        return groupBox
