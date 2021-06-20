# Python
from platform import system
import numpy as np


# PyPrag
from pyqtgraph.Qt import QtWidgets
from .player import Player

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

        self._player = Player(
            self._wav[0], self._wav[1]
        )  # FIXME: we should find a way to get rid of the filename

    def play(self):
        # Play subpart
        self._player.play()

    def pause(self):
        # Play subpart
        self._player.pauseResume()

    def stop(self):
        self._player.stop()

    def loop(self):
        self._player.loop()
