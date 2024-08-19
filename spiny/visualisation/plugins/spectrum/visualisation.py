# PyQTGraph
from pyqtgraph.Qt import QtGui, QtWidgets

# SpINY
from spiny.gui.widgets import DataWidget


class SpectrogramPlotWidget(DataWidget):
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

    def __init__(self, spectrum_extractor, parent=None, **kwargs):
        """
        Parameters
        ----------
        data: np.array
            matrix containing the data to render

        parent: pg.GraphicsObject
            the parent object

        kwargs: kwargs
            arguments passed to pg.PlotWidget

        """
        super().__init__(parent)
        color = QtWidgets.QApplication.instance().palette().color(QtGui.QPalette.Base)
        self.setBackground(color)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.enableMouse(False)

        # NOTE: needed to conserve the colormap
        self._ticks = None

        self._spectrum_extractor = spectrum_extractor

    def refresh(self):

        # 1. translate to the minimal frequency
        tr = QtGui.QTransform()
        min_y = self._spectrum_extractor._cutoff[0]
        tr.translate(0, min_y)

        # 2. scale
        y_scale = self._spectrum_extractor._cutoff[1] - self._spectrum_extractor._cutoff[0]
        y_scale /= self._spectrum_extractor._spectrum.shape[1]
        tr.scale(self._spectrum_extractor._frameshift * 0.001, y_scale)

        # Generate image item
        self._imageItem.setImage(self._spectrum_extractor._spectrum)
        self._imageItem.setTransform(tr)

        # Set the limits to focus the rendering
        self._plotItem.setLimits(
            minYRange=0,
            maxYRange=self._spectrum_extractor._spectrum.shape[1] * y_scale,
            yMin=0,
            yMax=self._spectrum_extractor._spectrum.shape[1] * y_scale,
            xMin=0,
            xMax=self._spectrum_extractor._frameshift * 0.001 * self._spectrum_extractor._spectrum.shape[0],
        )

        # Update the ticks and the histogram
        if self._ticks is not None:
            self.setTicks(self._ticks)

    def setTicks(self, ticks):
        self._ticks = ticks
        self._histItem.gradient.restoreState({"mode": "rgb", "ticks": ticks})
        # FIXME: self._histItem.plot.setLogMode(False, True)
