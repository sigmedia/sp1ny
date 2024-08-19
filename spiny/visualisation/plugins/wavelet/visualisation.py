# PyQTGraph
from pyqtgraph.Qt import QtGui, QtWidgets

# SpINY
from spiny.gui.widgets import DataWidget


class WaveletPlotWidget(DataWidget):
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
        super().__init__(parent)
        color = QtWidgets.QApplication.instance().palette().color(QtGui.QPalette.Base)
        self.setBackground(color)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.enableMouse(False)

        self._wavelet_extractor = wavelet_extractor

        # NOTE: needed to conserve the colormap
        self._ticks = None

    def refresh(self):

        scale_distance_hz = self._wavelet_extractor._scale_distance * 1000
        tr = QtGui.QTransform()
        y_scale = self._wavelet_extractor._num_scales * scale_distance_hz
        y_scale /= self._wavelet_extractor._wavelet.shape[1]
        tr.scale(self._wavelet_extractor._frameshift, y_scale)

        # Update Image
        self._imageItem.setImage(self._wavelet_extractor._wavelet)
        self._imageItem.setTransform(tr)

        # Set time and frequency axes
        self._plotItem.setLimits(
            minYRange=0,
            maxYRange=self._wavelet_extractor._num_scales * scale_distance_hz,
            yMin=0,
            yMax=self._wavelet_extractor._num_scales * scale_distance_hz,
            xMin=0,
            xMax=self._wavelet_extractor._frameshift * self._wavelet_extractor._wavelet.shape[0],
        )

        if self._ticks is not None:
            self.setTicks(self._ticks)

    def setTicks(self, ticks):
        self._ticks = ticks
        self._histItem.gradient.restoreState({"mode": "rgb", "ticks": ticks})
