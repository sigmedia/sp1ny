from pyqtgraph.Qt import QtWidgets, QtCore, QtGui
from spiny.core import DataController

from spiny.annotations import get_controller as get_annotation_controller


class WaveletController(DataController):
    def __init__(self, extractor, widget):
        self._name = "Wavelet"
        self._extractor = extractor
        self._widget = widget
        self._panel_built = False
        get_annotation_controller().list_registered_modules.add(self._tier_list_updated)

    def setWavPlot(self, wav_plot):
        self._wav_plot = wav_plot

    def extract(self):
        if self._panel_built:
            try:
                self._updateExtractorParameters()
            except ValueError as ex:
                QtWidgets.QMessageBox.warning(None, "Wavelet configuration", str(ex))
                return
        self._extractor.extract()
        self.refresh()

    def _updateExtractorParameters(self):
        """Copy the values of the control panel to the extractor

        Raises
        ------
        ValueError
            if a value is missing or inconsistent
        """

        def read(widget, name):
            try:
                return float(widget.text())
            except ValueError:
                raise ValueError(f'{name} must be a number (got "{widget.text()}")')

        min_f0 = read(self.min_f0, "min F0")
        max_f0 = read(self.max_f0, "max F0")
        if not 0 < min_f0 < max_f0:
            raise ValueError(f"F0 limits must satisfy 0 < min F0 < max F0 (got {min_f0} and {max_f0})")

        self._extractor._min_f0 = min_f0
        self._extractor._max_f0 = max_f0
        self._extractor._voicing = float(self.voicing.value())
        self._extractor._harmonics = float(self.harmonics.value())
        self._extractor._weight_f0 = read(self.wF0, "F0 weight")
        self._extractor._weight_energy = read(self.wEnergy, "Energy weight")
        self._extractor._combination = "product" if self.mul_feats.isChecked() else "sum"

    def setControlPanel(self, panel):

        # Create the main layout
        box_layout = QtWidgets.QVBoxLayout()
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Add different feature group part
        box_layout.addWidget(self.setF0Limits())
        box_layout.addWidget(self.prosodicFeats())
        box_layout.addWidget(self.featureCombination())
        # box_layout.addWidget(self.weight())
        box_layout.addWidget(self.signalTiers())
        box_layout.addWidget(self.createTierList())

        bExtract = QtWidgets.QPushButton("Extract")
        bExtract.clicked.connect(self.extract)
        bExtract.setDefault(False)
        bExtract.setAutoDefault(False)
        box_layout.addWidget(bExtract)

        scroll = QtWidgets.QScrollArea()
        # scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)

        configuration_widget = QtWidgets.QWidget()
        configuration_widget.setLayout(box_layout)
        scroll.setWidget(configuration_widget)

        # Create the groupbox
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(scroll)

        main_group_box = QtWidgets.QGroupBox("Wavelet configuration")
        main_group_box.setLayout(main_layout)
        panel.addWidget(main_group_box)

        self._panel_built = True
        self.populateTierList()

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
        self.min_f0 = QtWidgets.QLineEdit(str(self._extractor._min_f0))
        self.min_f0.setValidator(QtGui.QDoubleValidator(1.0, 2000.0, 1, self.min_f0))
        self.min_f0.setPlaceholderText("min F0 (Hz)")

        # Max F0
        self.max_f0 = QtWidgets.QLineEdit(str(self._extractor._max_f0))
        self.max_f0.setValidator(QtGui.QDoubleValidator(1.0, 2000.0, 1, self.max_f0))
        self.max_f0.setPlaceholderText("max F0 (Hz)")

        # Voicing
        self.voicing = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.voicing.setRange(0, 100)
        self.voicing.setSliderPosition(int(self._extractor._voicing))

        # Harmonics
        self.harmonics = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.harmonics.setRange(0, 100)
        self.harmonics.setSliderPosition(int(self._extractor._harmonics))
        self.harmonics.setVisible(False)

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
        self.wF0 = QtWidgets.QLineEdit(str(self._extractor._weight_f0))
        self.wF0.setValidator(QtGui.QDoubleValidator(0.0, 10.0, 2, self.wF0))

        # Energy widgets
        l2 = QtWidgets.QLabel("Energy")
        self.wEnergy = QtWidgets.QLineEdit(str(self._extractor._weight_energy))
        self.wEnergy.setValidator(QtGui.QDoubleValidator(0.0, 10.0, 2, self.wEnergy))

        # Duration widgets
        l3 = QtWidgets.QLabel("Duration")
        self.wDuration = QtWidgets.QLineEdit("0.0")
        self.wDuration.setEnabled(False)  # TODO: duration signal not implemented yet
        self.wDuration.setToolTip("The duration signal is not implemented yet")

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
        self._signal_tiers_list = QtWidgets.QListWidget()
        self._signal_tiers_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        # NOTE: self._signal_tiers_list.clicked.connect(self.onSignalRate)

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
        box.addWidget(self._signal_tiers_list)
        box.addWidget(self.diffDur)
        box.addWidget(self.signalRate)
        box.addWidget(self.bump)
        groupBox = QtWidgets.QGroupBox("Tier(s) for Duration Signal")
        # groupBox.setMaximumSize(400, 150)  # FIXME: see for not having hardcoded size
        groupBox.setLayout(box)
        groupBox.setToolTip("The duration signal is not implemented yet")
        groupBox.setEnabled(False)  # TODO: duration signal not implemented yet

        return groupBox

    def createTierList(self):
        groupBox = QtWidgets.QGroupBox("Tier for Prosody Annotation")
        self.tierlist = QtWidgets.QComboBox()
        # NOTE: self.tierlist.activated.connect(self.onTierChanged)
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.tierlist)
        groupBox.setLayout(vbox)
        return groupBox

    # reading of textgrids and lab, use previously selected tiers
    def populateTierList(self):

        # clear selection
        self.tierlist.clear()
        self._signal_tiers_list.clear()

        for k in get_annotation_controller().model.annotations.keys():
            self.tierlist.addItem(k)
            self._signal_tiers_list.addItem(k)

    def _tier_list_updated(self):
        try:
            self.populateTierList()
        except Exception:  # TODO: yeeek
            pass

    def weight(self):
        groupBox = QtWidgets.QGroupBox("frequency / time resolution")
        groupBox.setToolTip(
            "Interpolation between Mexican Hat wavelet (left) and Gaussian filter / scale-space (right)."
        )
        self._weight_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._weight_slider.sliderReleased.connect(self.onWeightChanged)

        hbox = QtWidgets.QVBoxLayout()
        hbox.addWidget(self._weight_slider)
        groupBox.setLayout(hbox)
        groupBox.setVisible(False)
        return groupBox

    def featureCombination(self):

        groupBox = QtWidgets.QGroupBox("Feature Combination Method")

        # NOTE: parented to the group box, otherwise the button group is garbage collected
        self._combination_method = QtWidgets.QButtonGroup(groupBox)

        self.sum_feats = QtWidgets.QRadioButton("sum")
        self.mul_feats = QtWidgets.QRadioButton("product")
        self.sum_feats.setChecked(self._extractor._combination == "sum")
        self.mul_feats.setChecked(self._extractor._combination == "product")

        self._combination_method.addButton(self.sum_feats)
        self._combination_method.addButton(self.mul_feats)

        # self.sum_feats.clicked.connect(self.onSignalRate)
        # self.mul_feats.clicked.connect(self.onSignalRate)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.sum_feats)
        hbox.addWidget(self.mul_feats)
        groupBox.setLayout(hbox)
        groupBox.setVisible(True)

        return groupBox
