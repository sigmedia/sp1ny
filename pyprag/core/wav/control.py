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
        bPlay = QtWidgets.QPushButton(PlayerControllerWidget.BUTTON_GLYPHS[0], self)
        bPlay.clicked.connect(self.play)
        bPlay.setDefault(False)
        bPlay.setAutoDefault(False)

        # Define stop button
        bPause = QtWidgets.QPushButton(PlayerControllerWidget.BUTTON_GLYPHS[1], self)
        bPause.clicked.connect(self.pause)
        bPause.setDefault(False)
        bPause.setAutoDefault(False)

        # Define stop button
        bStop = QtWidgets.QPushButton(PlayerControllerWidget.BUTTON_GLYPHS[2], self)
        bStop.clicked.connect(self.stop)
        bStop.setDefault(False)
        bStop.setAutoDefault(False)

        # Define loop button
        bLoop = QtWidgets.QPushButton(PlayerControllerWidget.BUTTON_GLYPHS[3], self)
        bLoop.clicked.connect(self.loop)
        bLoop.setDefault(False)
        bLoop.setAutoDefault(False)

        # Define device selection box
        devices = sd.query_devices()
        device_names = [device['name'] for device in devices]
        boxDevices = QtWidgets.QComboBox()
        boxDevices.addItems(device_names)
        sysdefaultIndex = [i for i, s in enumerate(device_names) if 'sysdefault' in s][0]
        boxDevices.setCurrentIndex(sysdefaultIndex)
        boxDevices.currentIndexChanged.connect(self.device_changed)

        player_layout = QtWidgets.QHBoxLayout()
        player_layout.addWidget(bPlay)
        player_layout.addWidget(bPause)
        player_layout.addWidget(bStop)
        player_layout.addWidget(bLoop)
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

    def stop(self):
        player.stop()

    def loop(self):
        player.toggleLoop()

    def device_changed(self, index):
        player._device = index
