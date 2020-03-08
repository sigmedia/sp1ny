# PyQTGraph
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtWidgets

# SpINY
from spiny.gui.items import SelectablePlotItem


class RawDataPlotWidget(pg.PlotWidget):
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
        color = QtWidgets.QApplication.instance().palette().color(QtGui.QPalette.Base)
        pg.GraphicsView.__init__(self, parent, background=color)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.enableMouse(False)

        # Save reference to data
        self._data_extractor = data_extractor

        # NOTE: needed to conserve the colormap
        self._ticks = None

    def refresh(self):
        self._img = pg.ImageItem()
        self._img.setImage(self._data_extractor._data.T)

        tr = QtGui.QTransform()
        tr.scale(self._data_extractor._frameshift * 0.001, 1)
        self._img.setTransform(tr)

        # Generate plot
        self.plotItem = SelectablePlotItem()
        self.plotItem.getViewBox().addItem(self._img)
        self.setCentralItem(self.plotItem)

        # Set the limits to prevent bad (FIXME: hardcoded values)
        self.plotItem.setLimits(
            minYRange=0,
            maxYRange=self._data_extractor._data.shape[1],
            yMin=0,
            yMax=self._data_extractor._data.shape[1],
            xMin=0,
            xMax=self._data_extractor._frameshift * 0.001 * self._data_extractor._data.shape[0],
        )

        if self._ticks is not None:
            self.setTicks(self._ticks)

    def setTicks(self, ticks):
        self._ticks = ticks

        # Define and assign histogram
        self.hist = pg.HistogramLUTWidget()
        self.hist.setImageItem(self._img)
        self.hist.gradient.restoreState({"mode": "rgb", "ticks": ticks})
