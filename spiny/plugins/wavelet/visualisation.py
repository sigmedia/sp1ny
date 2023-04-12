# PyQTGraph
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtWidgets

# PyPrag
from spiny.gui.items import SelectablePlotItem


class WaveletPlotWidget(pg.PlotWidget):
    """Image plot widget allowing to highlight some regions

    Attributes
    ----------
    _data : np.array
        matrix containing the data rendered

    plotItem : spiny.gui.items.SelectablePlotItem
        The plot item contained in the widget

    hist : pg.HistogramLUTWidget
        The histogram widget to control the image colorimetrie
    """

    def __init__(self, wavelet_extractor, parent=None, **kwargs):
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
        color = QtWidgets.QApplication.instance().palette().color(QtGui.QPalette.Base)
        pg.GraphicsView.__init__(self, parent, background=color)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.enableMouse(False)

        self._wavelet_extractor = wavelet_extractor

        # NOTE: needed to conserve the colormap
        self._ticks = None

    def refresh(self):
        self._img = pg.ImageItem()
        self._img.setImage(self._wavelet_extractor._wavelet.T)

        tr = QtGui.QTransform()
        # 2. scale
        y_scale = self._wavelet_extractor._num_scales * self._wavelet_extractor._scale_distance
        y_scale /= self._wavelet_extractor._wavelet.shape[1]
        tr.scale(self._wavelet_extractor._frameshift, y_scale)
        self._img.setTransform(tr)

        # Generate plot
        self.plotItem = SelectablePlotItem()
        self.plotItem.getViewBox().addItem(self._img)
        self.setCentralItem(self.plotItem)

        if self._ticks is not None:
            self.setTicks(self._ticks)

    def setTicks(self, ticks):
        self._ticks = ticks
        # Define and assign histogram
        self.hist = pg.HistogramLUTWidget()
        self.hist.setImageItem(self._img)
        self.hist.gradient.restoreState({"mode": "rgb", "ticks": ticks})
