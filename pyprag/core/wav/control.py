# Python
from platform import system

# Python SoundDevice
import sounddevice as sd

# PyPrag
from pyqtgraph.Qt import QtWidgets
from .player import player


class PlayerControllerWidget(QtWidgets.QWidget):
    """ """

    BUTTON_GLYPHS = ("▶", "⏯", "⏹", "Loop") if system() != "Windows" else ("▶️", "⏯️", "⏹️", "Loop️")

    def __init__(self, filename, wav, parent=None, background="default", **kwargs):
        super().__init__(parent, **kwargs)

        self._filename = filename
        player.loadNewWav(wav[0], wav[1])

        # Define play button
        self.bPlay = QtWidgets.QPushButton(PlayerControllerWidget.BUTTON_GLYPHS[0], self)
        self.bPlay.clicked.connect(self.play)
        self.bPlay.setDefault(False)
        self.bPlay.setAutoDefault(False)

        # Define stop button
        self.bPause = QtWidgets.QPushButton(PlayerControllerWidget.BUTTON_GLYPHS[1], self)
        self.bPause.clicked.connect(self.pause)
        self.bPause.setDefault(False)
        self.bPause.setAutoDefault(False)

        # Define stop button
        self.bStop = QtWidgets.QPushButton(PlayerControllerWidget.BUTTON_GLYPHS[2], self)
        self.bStop.clicked.connect(self.stop)
        self.bStop.setDefault(False)
        self.bStop.setAutoDefault(False)

        # Define loop button
        self.bLoop = QtWidgets.QPushButton(PlayerControllerWidget.BUTTON_GLYPHS[3], self)
        self.bLoop.clicked.connect(self.loop)
        self.bLoop.setDefault(False)
        self.bLoop.setAutoDefault(False)

        # Define device selection box
        devices = sd.query_devices()
        device_names = [device['name'] for device in devices]
        boxDevices = QtWidgets.QComboBox()
        boxDevices.addItems(device_names)
        sysdefaultIndex = [i for i, s in enumerate(device_names) if 'sysdefault' in s][0]
        boxDevices.setCurrentIndex(sysdefaultIndex)
        boxDevices.currentIndexChanged.connect(self.device_changed)

        player_layout = QtWidgets.QHBoxLayout()
        player_layout.addWidget(self.bPlay)
        player_layout.addWidget(self.bPause)
        player_layout.addWidget(self.bStop)
        player_layout.addWidget(self.bLoop)
        player_layout.addWidget(boxDevices)
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
            self.bPause.setFlat(True)
        else:
            self.bPause.setFlat(False)

    def stop(self):
        player.stop()

    def loop(self):
        player.toggleLoop()
        if player._loop_activated:
            self.bLoop.setFlat(True)
        else:
            self.bLoop.setFlat(False)

    def device_changed(self, index):
        player._device = index
