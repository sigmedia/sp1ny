# Python
from platform import system

# Python SoundDevice
import sounddevice as sd

# SpINY
from pyqtgraph.Qt import QtCore, QtWidgets, isQObjectAlive
from .player import player


class PlayerControllerWidget(QtWidgets.QWidget):
    """ """

    BUTTON_GLYPHS = ("▶", "⏯", "⏹", "Loop") if system() != "Windows" else ("▶️", "⏯️", "⏹️", "Loop️")

    def __init__(self, parent=None, background="default", **kwargs):
        super().__init__(parent, **kwargs)

        # Define play button
        self._bPlay = QtWidgets.QPushButton(PlayerControllerWidget.BUTTON_GLYPHS[0], self)
        self._bPlay.clicked.connect(self.play)
        self._bPlay.setDefault(False)
        self._bPlay.setAutoDefault(False)

        # Define stop button
        self._bPause = QtWidgets.QPushButton(PlayerControllerWidget.BUTTON_GLYPHS[1], self)
        self._bPause.clicked.connect(self.pause)
        self._bPause.setDefault(False)
        self._bPause.setAutoDefault(False)

        # Define stop button
        self._bStop = QtWidgets.QPushButton(PlayerControllerWidget.BUTTON_GLYPHS[2], self)
        self._bStop.clicked.connect(self.stop)
        self._bStop.setDefault(False)
        self._bStop.setAutoDefault(False)

        # Define loop button
        self._bLoop = QtWidgets.QPushButton(PlayerControllerWidget.BUTTON_GLYPHS[3], self)
        self._bLoop.setStyleSheet("background-color: #EAA799;")
        self._bLoop.clicked.connect(self.loop)
        self._bLoop.setDefault(False)
        self._bLoop.setAutoDefault(False)

        # Get devices information (the default output index is -1 when there is no output device)
        devices = sd.query_devices()
        self._devices = dict()
        default_device_index = sd.default.device[1]
        default_device = None
        for index, device in enumerate(devices):
            if device["max_output_channels"] <= 0:  # NOTE: only consider output devices!
                continue
            if "index" in device:
                index = int(device["index"])

            self._devices[device["name"]] = index
            if index == default_device_index:
                default_device = device["name"]

        # Generation Device ComboBox
        self._boxDevices = QtWidgets.QComboBox()
        self._boxDevices.addItems(self._devices.keys())
        if default_device is not None:
            self._boxDevices.setCurrentText(default_device)

        # Without any output device, playback controls are useless
        if not self._devices:
            self._boxDevices.addItem("No output device")
            for button in (self._bPlay, self._bPause, self._bStop, self._bLoop, self._boxDevices):
                button.setEnabled(False)
        self._boxDevices.currentTextChanged.connect(self.device_changed)

        # Define volume slider
        self._lVolume = QtWidgets.QLabel("100%", self)
        self._lVolume.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._lVolume.setMinimumWidth(80)
        self._sVolume = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._sVolume.setRange(0, 100)
        self._sVolume.setValue(100)
        self._sVolume.setTracking(True)
        self._sVolume.valueChanged.connect(self.volume_changed)

        player_layout = QtWidgets.QHBoxLayout()
        player_layout.addWidget(self._bPlay)
        player_layout.addWidget(self._bPause)
        player_layout.addWidget(self._bStop)
        player_layout.addWidget(self._bLoop)
        player_layout.addSpacing(15)
        player_layout.addWidget(QtWidgets.QLabel("Output Device"))
        player_layout.addWidget(self._boxDevices)
        player_layout.addSpacing(15)
        player_layout.addWidget(QtWidgets.QLabel("Volume"))
        player_layout.addWidget(self._sVolume)
        player_layout.addWidget(self._lVolume)
        self.setLayout(player_layout)

    def play(self):
        # Play subpart
        try:
            player.play()
        except sd.PortAudioError as ex:
            QtWidgets.QMessageBox.warning(self, "Playback error", f"The audio device cannot play this signal:\n{ex}")

    def pause(self):
        # Play subpart
        player.pauseResume()
        if player.is_paused:
            self._bPause.setFlat(True)
        else:
            self._bPause.setFlat(False)

    def stop(self):
        self._bPause.setFlat(False)
        player.stop()

    def loop(self):
        player.toggleLoop()
        if player.loop_activated:
            self._bLoop.setStyleSheet("background-color: #B3EDB1;")
        else:
            self._bLoop.setStyleSheet("background-color: #EAA799;")

    def device_changed(self, name):
        index = self._devices[name]
        try:
            player.setDevice(index)
        except sd.PortAudioError as ex:
            QtWidgets.QMessageBox.warning(self, "Output device", f'The device "{name}" cannot be used:\n{ex}')
            self._boxDevices.blockSignals(True)
            self._boxDevices.setCurrentText(self._deviceName(player.device))
            self._boxDevices.blockSignals(False)

    def _deviceName(self, index):
        if index is None:
            index = sd.default.device[1]
        for name, cur_index in self._devices.items():
            if cur_index == index:
                return name
        return ""

    def volume_changed(self):
        player.volume = self._sVolume.value() / 100
        self._lVolume.setText(f"{self._sVolume.value()}%")


class ControlLayout(QtWidgets.QVBoxLayout):
    def __init__(self, parent):
        super().__init__(parent)

        # Create the main layout
        box_layout = QtWidgets.QVBoxLayout()
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Prepare scrollbar
        scroll = QtWidgets.QScrollArea()
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)

        # Generate the necessary widgets
        self._file_box = self._generate_file_box()
        self._eq_widget = EqWidget(None, (9, 1))  # FIXME: place holder, the equalizer is not implemented
        self._eq_widget.setEnabled(False)
        self._eq_widget.setToolTip("The equalizer is not implemented yet")

        # Add the widgets
        box_layout.addWidget(self._file_box)
        box_layout.addWidget(self._eq_widget)

        # Generate Configuration Widget
        configuration_widget = QtWidgets.QWidget()
        configuration_widget.setLayout(box_layout)
        scroll.setWidget(configuration_widget)

        # Finalize the layout
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.addWidget(scroll)

    def _generate_file_box(self):
        file_box_layout = QtWidgets.QGridLayout()
        file_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Start time
        l1 = QtWidgets.QLabel("Current File")
        self._wCurrentFile = QtWidgets.QLineEdit("none")
        self._wCurrentFile.setEnabled(False)
        file_box_layout.addWidget(l1, 1, 0)
        file_box_layout.addWidget(self._wCurrentFile, 1, 1)

        self._bLoadFile = QtWidgets.QPushButton("Load File")
        self._bLoadFile.setEnabled(False)  # Enabled once a load handler is set (see setLoadHandler)
        self._bLoadFile.setDefault(False)
        self._bLoadFile.setAutoDefault(False)
        file_box_layout.addWidget(self._bLoadFile)

        self._bSaveFile = QtWidgets.QPushButton("Save File")
        self._bSaveFile.setEnabled(False)  # TODO: nothing modifies the signal yet, so there is nothing to save
        self._bSaveFile.setToolTip("Saving audio is not implemented yet")
        self._bSaveFile.setDefault(False)
        self._bSaveFile.setAutoDefault(False)
        file_box_layout.addWidget(self._bSaveFile)

        file_box = QtWidgets.QGroupBox("Audio File")
        file_box.setLayout(file_box_layout)

        return file_box

    def setLoadHandler(self, handler):
        """Define the function called by the "Load File" button"""
        self._bLoadFile.clicked.connect(handler)
        self._bLoadFile.setEnabled(True)

    def setCurrentFile(self, filename):
        self._wCurrentFile.setText(filename)


class EqWidget(QtWidgets.QGroupBox):
    def __init__(self, parent, wav):
        super().__init__(title="Equalizer", parent=parent)

        self._signal = wav[0]
        self._sampling_rate = wav[1]

        slider_layout = self._define_sliders()
        self._apply_button = QtWidgets.QPushButton("Apply")
        overall_layout = QtWidgets.QVBoxLayout()
        overall_layout.addLayout(slider_layout)
        overall_layout.addWidget(self._apply_button)
        self.setLayout(overall_layout)

    def _define_sliders(self):

        self._frequencies = [50, 200, 1000, 2000, 4000, 8000, 16000]
        self._slider_array = []

        layout = QtWidgets.QHBoxLayout()

        prev_freq = 0
        for freq in self._frequencies:

            cur_slider = EqSlider(prev_freq, freq, self)
            layout.addWidget(cur_slider)
            prev_freq = freq

        return layout


class EqSlider(QtWidgets.QWidget):
    def __init__(self, lower_freq, upper_freq, parent=None):
        super().__init__(parent=parent)
        self._verticalLayout = QtWidgets.QVBoxLayout(self)
        self._label = QtWidgets.QLabel(self)
        self._verticalLayout.addWidget(self._label)
        self._horizontalLayout = QtWidgets.QHBoxLayout()
        spacerItem = QtWidgets.QSpacerItem(0, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self._horizontalLayout.addItem(spacerItem)
        self._slider = QtWidgets.QSlider(self)
        self._slider.setOrientation(QtCore.Qt.Vertical)
        self._horizontalLayout.addWidget(self._slider)
        spacerItem1 = QtWidgets.QSpacerItem(0, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self._horizontalLayout.addItem(spacerItem1)
        self._verticalLayout.addLayout(self._horizontalLayout)
        self.resize(self.sizeHint())

        self._slider.setMinimum(-120)
        self._slider.setMaximum(0)
        self._slider.setValue(0)
        self._slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self._slider.setTickInterval(10)  # FIXME: hardcoded

        self._lower_freq = lower_freq
        self._upper_freq = upper_freq

        self.setLabelValue(upper_freq)

    def setLabelValue(self, upper_freq):
        if upper_freq >= 1000:
            self._label.setText(f"< {int(upper_freq/1000):2d}k")
        else:
            self._label.setText(f"< {upper_freq}")


_controller = None


def get_controller() -> ControlLayout:
    """Return the audio control layout, creating it on first use (a QApplication must exist)

    The layout is also re-created if its Qt object has been deleted (e.g. when the window owning it was closed).
    """
    global _controller
    # NOTE: the layout wrapper can outlive the widgets it manages, so check one of them too
    if (_controller is None) or (not isQObjectAlive(_controller)) or (not isQObjectAlive(_controller._file_box)):
        _controller = ControlLayout(None)
    return _controller
