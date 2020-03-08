# Python
from platform import system

# Python SoundDevice
import sounddevice as sd

# SpINY
from pyqtgraph.Qt import QtCore, QtWidgets
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

        # Get devices information
        devices = sd.query_devices()
        self._devices = dict()
        default_device_index = sd.query_hostapis()[0].get("default_" + "output".lower() + "_device")
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
        self._boxDevices.setCurrentText(default_device)
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

        # player.add_position_handler(self.update_position)

    def update_position(self, position):
        print(f"{float(position) / player._sampling_rate}", end="\r")

    def play(self):
        # Play subpart
        player.play()

    def pause(self):
        # Play subpart
        player.pauseResume()
        if player._is_paused:
            self._bPause.setFlat(True)
        else:
            self._bPause.setFlat(False)

    def stop(self):
        player._is_paused = False
        self._bPause.setFlat(False)
        player.stop()

    def loop(self):
        player.toggleLoop()
        if player._loop_activated:
            self._bLoop.setStyleSheet("background-color: #B3EDB1;")
        else:
            self._bLoop.setStyleSheet("background-color: #EAA799;")

    def device_changed(self, name):
        index = self._devices[name]
        player._device = index

    def volume_changed(self):
        player._player_volume = self._sVolume.value() / 100
        self._lVolume.setText(f"{self._sVolume.value()}%")
