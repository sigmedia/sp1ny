# Numerical
import numpy as np

# PyQTGraph
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtWidgets
from pyqtgraph.dockarea import Dock

# SpINY
from spiny.ui.segment import SelectablePlotItem
from .player import player

###############################################################################
# Classes
###############################################################################


class WavPlotWidget(pg.PlotWidget):
    """Image plot widget allowing to highlight some regions

    Attributes
    ----------
    _wav : tuple(np.array, int)
        The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

    plotItem : spiny.gui.items.SelectablePlotItem
        The plot item contained in the widget

    """

    def __init__(self, parent=None, **kwargs):
        """
        Parameters
        ----------
        wav : tuple(np.array, int)
            The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.
        ticks: TODO
            color map ticks

        parent: pg.GraphicsObject
            the parent object

        background: str
            the background of the plot

        kwargs: kwargs
            arguments passed to pg.PlotWidget

        """
        super().__init__(parent=parent)

        # Save reference to wav

        # Prepare plot item
        self.plotItem = SelectablePlotItem(
            lock_y_axis=True,
            # values=[min_y, max_y],
            default_padding=0,
            **kwargs,
        )
        self.setCentralItem(self.plotItem)

        # Define the limits to constraint the zoom
        T = player._wav.shape[0] / player._sampling_rate
        self.plotItem.setLimits(xMin=0, xMax=T, minXRange=0, maxXRange=T)
        self.plotItem.setYRange(-1, 1)
        self.plotItem.setXRange(0, T)
        v_bar = pg.InfiniteLine(pos=0, movable=False, angle=90, pen=pg.mkPen({"color": "#F00", "width": 2}))

        def _update_position_handler(position):
            v_bar.setValue(position)

        player.add_position_handler(_update_position_handler)
        self.plotItem.addItem(v_bar)

        # Initial rendering
        self.updateVisibleRegions()

        # Connect the rangeChanged signal to update visible regions
        self.getPlotItem().getViewBox().sigXRangeChanged.connect(self.updateVisibleRegions)

    def updateVisibleRegions(self):
        # Get the current visible range
        view_range = self.getPlotItem().getViewBox().viewRange()
        x_min, x_max = view_range[0]
        x_min = int(x_min * player._sampling_rate)
        x_max = int(x_max * player._sampling_rate)
        step = (x_max - x_min) // 10000  # FIXME: number of points being hardcoded is bad
        if step < 1:
            step = 1

        # ???
        self.getPlotItem().clear()

        # Plot a nice version of the current one
        x = np.arange(x_min, x_max, step)
        # y = decimate([x_min:x_max], step)
        y = player._wav.squeeze()[x]

        color = QtWidgets.QApplication.instance().palette().color(QtGui.QPalette.Text)
        self.plotItem.plot(x / player._sampling_rate, y, pen=color)


class WavDock(Dock):
    """Dock containing a data surface plot (matrix data for now) and the corresponding waveform

    Attributes
    ----------
    data : np.array
        matrix containing the data to render

    wav : tuple(np.array, int)
        The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

    data_plot :
        The plot item rendering the data part

    wav_plot :
        The plot item rendering the waveform
    """

    def __init__(self, name, size):
        """
        Parameters
        ----------
        name : string
            The name of the dock

        size : TODO
            The size of the widget

        data : np.array
            The data to render

        wav : tuple(np.array, int)
            The signal information as loaded using librosa.
            The tuple contain an array of samples and the sample rate.

        frameshift : float
            The frameshift used to extract the data from the signal

        ticks : TODO
            The color map ticks

        """
        super().__init__(name=name, size=size, autoOrientation=False)
        self.__plotWav()

        # Label space
        self.wav_plot.getAxis("left").setWidth(50)

    def __plotWav(self):
        """Helper to plot the waveform

        Parameters
        ----------
        max_dur : float
          The maximum duration in seconds. It is mainly used in the case
          that the annotations require more space than the waveform
        """

        self.wav_plot = WavPlotWidget(name="%s waveform" % self.name)
        self.addWidget(self.wav_plot)

    def setOrientation(self, o="auto", force=False):
        """
        Sets the orientation of the title bar for this Dock.
        Must be one of 'auto', 'horizontal', or 'vertical'.
        By default ('auto'), the orientation is determined
        based on the aspect ratio of the Dock.
        """
        # setOrientation may be called before the container is set in some cases
        # (via resizeEvent), so there's no need to do anything here until called
        # again by containerChanged
        if self.container() is None:
            return

        if o == "auto" and self.autoOrient:
            if self.container().type() == "tab":
                o = "horizontal"
            elif self.width() > self.height() * 1.5:
                o = "vertical"
            else:
                o = "horizontal"

        if force and self.orientation != o:
            self.orientation = o
            self.label.setOrientation(o)
            self.updateStyle()
