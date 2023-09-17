# PyQTGraph
from pyqtgraph.Qt import QtGui, QtWidgets

# SpINY
from spiny.gui.widgets import DataWidget


class RawDataPlotWidget(DataWidget):
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

    def __init__(self, data_extractor, parent=None, **kwargs):
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

        # Save reference to data
        self._data_extractor = data_extractor

        # NOTE: needed to conserve the colormap
        self._ticks = None

    def refresh(self):
        tr = QtGui.QTransform()
        tr.scale(self._data_extractor._frameshift * 0.001, 1)

        # Generate image item
        self._imageItem.setImage(self._data_extractor._data.T)
        self._imageItem.setTransform(tr)

        # Set the limits to focus the rendering
        self._plotItem.setLimits(
            minYRange=0,
            maxYRange=self._data_extractor._data.shape[1],
            yMin=0,
            yMax=self._data_extractor._data.shape[1],
            xMin=0,
            xMax=self._data_extractor._frameshift * 0.001 * self._data_extractor._data.shape[0],
        )

        # Update the ticks and the histogram
        if self._ticks is not None:
            self.setTicks(self._ticks)

    def setTicks(self, ticks):
        self._ticks = ticks
        self._histItem.gradient.restoreState({"mode": "rgb", "ticks": ticks})
        # self._histItem.setLevels(self._spectrum_extractor._spectrum_.min(), self.data.max())
