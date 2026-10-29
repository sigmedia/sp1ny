# Python
import numpy as np

# PyQTGraph
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from pyqtgraph.dockarea import Dock

# SpINY
from spiny.gui.items import SelectablePlotItem
from .player import player

###############################################################################
# Classes
###############################################################################


class WavPlotWidget(pg.PlotWidget):
    """Waveform plot of the signal loaded in the player, with region selection and a playback cursor

    Attributes
    ----------
    plotItem : spiny.gui.items.SelectablePlotItem
        The plot item contained in the widget
    """

    def __init__(self, parent=None, **kwargs):
        """
        Parameters
        ----------
        parent: QWidget
            the parent widget

        kwargs: kwargs
            arguments passed to spiny.gui.items.SelectablePlotItem
        """
        super().__init__(parent=parent)

        # Prepare plot item
        self.plotItem = SelectablePlotItem(
            lock_y_axis=True,
            # values=[min_y, max_y],
            default_padding=0,
            **kwargs,
        )
        self.setCentralItem(self.plotItem)
        color = QtWidgets.QApplication.instance().palette().color(QtGui.QPalette.Text)
        self._curve = self.plotItem.plot(pen=color)
        self.refresh()

        self._v_bar = pg.InfiniteLine(pos=0, movable=False, angle=90, pen=pg.mkPen({"color": "#F00", "width": 2}))
        self.plotItem.addItem(self._v_bar)

        # Poll the player position from the GUI thread (the audio thread must never touch Qt objects)
        self._position_timer = QtCore.QTimer(self)
        self._position_timer.setInterval(30)
        self._position_timer.timeout.connect(self._update_position)
        self._position_timer.start()

    def refresh(self):
        """(Re)draw the waveform of the signal currently loaded in the player"""
        x = np.arange(player.signal.shape[0]) / player.sampling_rate
        self._curve.setData(x, player.signal.squeeze())  # FIXME: duplicate things, find a way to get rid of this!

        # Define the limits to constraint the zoom
        T = player.duration
        self.plotItem.setLimits(
            yMin=-1,
            yMax=1,
            xMin=0,
            xMax=T,
            minXRange=0,
            maxXRange=T,
        )
        self.plotItem.setXRange(0, T, padding=0)

    def _update_position(self):
        position = player.position
        if self._v_bar.value() != position:
            self._v_bar.setValue(position)


class WavDock(Dock):
    """Dock containing the waveform of the signal loaded in the player

    Attributes
    ----------
    wav_plot : WavPlotWidget
        The widget rendering the waveform
    """

    def __init__(self, name, size):
        """
        Parameters
        ----------
        name : string
            The name of the dock

        size : tuple(int, int)
            The default size of the dock
        """
        Dock.__init__(self, name=name, size=size)
        self.__plotWav()

        # Label space
        self.wav_plot.getAxis("left").setWidth(50)

    def __plotWav(self):
        """Helper to create the waveform widget"""
        self.wav_plot = WavPlotWidget(name="%s waveform" % self.name)
        self.addWidget(self.wav_plot)
