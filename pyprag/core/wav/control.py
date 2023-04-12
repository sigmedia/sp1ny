# Python
from platform import system
import math

# Python SoundDevice
import sounddevice as sd

# PyPrag
from pyqtgraph.Qt import QtCore, QtWidgets
from .player import player


class PlayerControllerWidget(QtWidgets.QWidget):
    """ """

    BUTTON_GLYPHS = ("▶", "⏯", "⏹", "Loop") if system() != "Windows" else ("▶️", "⏯️", "⏹️", "Loop️")

    def __init__(self, filename, wav, parent=None, background="default", **kwargs):
        super().__init__(parent, **kwargs)

        self._filename = filename
        player.loadNewWav(wav[0], wav[1])

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
        self._bLoop.clicked.connect(self.loop)
        self._bLoop.setDefault(False)
        self._bLoop.setAutoDefault(False)

        # Define device selection box
        devices = sd.query_devices()
        device_names = [device['name'] for device in devices]
        self._boxDevices = QtWidgets.QComboBox()
        self._boxDevices.addItems(device_names)
        sysdefaultIndex = [i for i, s in enumerate(device_names) if 'sysdefault' in s][0]
        self._boxDevices.setCurrentIndex(sysdefaultIndex)
        self._boxDevices.currentIndexChanged.connect(self.device_changed)

        # Define volume slider
        self._lVolume = QtWidgets.QLabel('100', self)
        self._lVolume.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._lVolume.setMinimumWidth(80)
        self._sVolume = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._sVolume.setRange(0., 100.)
        self._sVolume.setValue(100.)
        self._sVolume.setTracking(True)
        self._sVolume.valueChanged.connect(self.volume_changed)

        player_layout = QtWidgets.QHBoxLayout()
        player_layout.addWidget(self._bPlay)
        player_layout.addWidget(self._bPause)
        player_layout.addWidget(self._bStop)
        player_layout.addWidget(self._bLoop)
        player_layout.addSpacing(15)
        player_layout.addWidget(self._boxDevices)
        player_layout.addSpacing(15)
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
            self._bLoop.setFlat(True)
        else:
            self._bLoop.setFlat(False)

    def device_changed(self, index):
        player._device = index

    def volume_changed(self):
        player._player_volume = self._sVolume.value() / 100
        self._lVolume.setText(str(self._sVolume.value()))
