# Python
from platform import system

# PyPrag
from pyqtgraph.Qt import QtWidgets
from .player import player


class PlayerWidget(QtWidgets.QWidget):
    """ """

    BUTTON_GLYPHS = ("▶", "⏯", "⏹", "Loop") if system() != "Windows" else ("▶️", "⏯️", "⏹️", "Loop️")

    def __init__(self, filename, wav, parent=None, background="default", **kwargs):
        super().__init__(parent, **kwargs)

        self._filename = filename
        self._wav = wav

        # Define play button
        bPlay = QtWidgets.QPushButton(PlayerWidget.BUTTON_GLYPHS[0], self)
        bPlay.clicked.connect(self.play)
        bPlay.setDefault(False)
        bPlay.setAutoDefault(False)

        # Define stop button
        bPause = QtWidgets.QPushButton(PlayerWidget.BUTTON_GLYPHS[1], self)
        bPause.clicked.connect(self.pause)
        bPause.setDefault(False)
        bPause.setAutoDefault(False)

        # Define stop button
        bStop = QtWidgets.QPushButton(PlayerWidget.BUTTON_GLYPHS[2], self)
        bStop.clicked.connect(self.stop)
        bStop.setDefault(False)
        bStop.setAutoDefault(False)

        # Define loop button
        bLoop = QtWidgets.QPushButton(PlayerWidget.BUTTON_GLYPHS[3], self)
        bLoop.clicked.connect(self.loop)
        bLoop.setDefault(False)
        bLoop.setAutoDefault(False)

        player_layout = QtWidgets.QHBoxLayout()
        player_layout.addWidget(bPlay)
        player_layout.addWidget(bPause)
        player_layout.addWidget(bStop)
        player_layout.addWidget(bLoop)
        self.setLayout(player_layout)

        player.loadNewWav(self._wav[0], self._wav[1])  # FIXME: we should find a way to get rid of the filename

        player.set_position_handler(self.update_position)

    def update_position(self, position):
        print(f"{position} / {self._wav[0].shape[0]}", end="\r")
        print(position)

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
