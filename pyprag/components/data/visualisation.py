# PyQTGraph
import pyqtgraph as pg
from pyqtgraph.dockarea import Dock
from pyqtgraph.Qt import QtGui

# PyPrag
from pyprag.gui.items import SelectablePlotItem


class SelectableImagePlotWidget(pg.PlotWidget):
    """Image plot widget allowing to highlight some regions

    Attributes
    ----------
    _data : np.array
        matrix containing the data rendered

    plotItem : pyprag.gui.items.SelectablePlotItem
        The plot item contained in the widget

    hist : pg.HistogramLUTWidget
        The histogram widget to control the image colorimetrie
    """

    def __init__(self, data, frameshift, ticks, max_y, parent=None, background="default", **kwargs):
        """
        Parameters
        ----------
        data: np.array
            matrix containing the data to render

        frameshift: float
            frameshift in senconds

        ticks: TODO
            color map ticks

        parent: pg.GraphicsObject
            the parent object

        background: str
            the background of the plot

        kwargs: kwargs
            arguments passed to pg.PlotWidget

        """
        pg.GraphicsView.__init__(self, parent, background)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        self.enableMouse(False)

        # Save reference to data
        self._data = data
        self._max_y = max_y

        # Generate image data
        img = pg.ImageItem()
        img.setImage(self._data.T)
        img.setTransform(QtGui.QTransform.fromScale(frameshift, 1.0 / (self._data.shape[1] / self._max_y)))

        # Define and assign histogram
        self.hist = pg.HistogramLUTWidget()
        self.hist.setImageItem(img)
        self.hist.gradient.restoreState({"mode": "rgb", "ticks": ticks})

        # Generate plot
        self.plotItem = SelectablePlotItem(**kwargs)
        self.plotItem.getViewBox().addItem(img)
        self.setCentralItem(self.plotItem)


class DataDock(Dock):
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

    def __init__(self, name, size, data, frameshift, ticks, wav):
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
            The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

        frameshift : float
            The frameshift used to extract the data from the signal

        ticks : TODO
            The color map ticks

        """
        Dock.__init__(self, name=name, size=size)

        self.data = data
        self.wav = wav
        # max_dur = self.data.shape[0] * frameshift

        self.__plotData(frameshift, ticks)

        # Label space
        self.data_plot.getAxis("left").setWidth(50)

    def __plotData(self, frameshift, ticks):
        """Helper to plot the data

        Parameters
        ----------
        frameshift : float
            The frameshift used to extract the signals

        ticks : TODO
            The color map ticks

        y_scale : int
            SHOULD NOT BE USED FOR NOW!

        """
        lim_factor = 1.1
        self.data_plot = SelectableImagePlotWidget(
            self.data,
            frameshift,
            ticks,
            self.wav[1] / 2.0,  # NOTE: max_y is imposed to be nyquist!
            name="%s coef" % self.name,
            wav=self.wav,
        )
        self.data_plot.setLimits(xMax=self.data.shape[0] * frameshift * lim_factor)
        self.data_plot.hideAxis("bottom")

        # Add plot
        # self.data_plot.disableAutoRange()
        self.addWidget(self.data_plot)
