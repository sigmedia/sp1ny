# PyQTGraph
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui

# PyPrag
from pyprag.gui.items import SelectablePlotItem


class RawDataPlotWidget(pg.PlotWidget):
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

    def __init__(self, data_extractor, parent=None, background="default", **kwargs):
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
        self._data_extractor = data_extractor

    def refresh(self):
        self._img = pg.ImageItem()
        self._img.setImage(self._data_extractor._data.T)

        self._img.scale(self._data_extractor._frameshift, 1)

        # Generate plot
        self.plotItem = SelectablePlotItem()
        self.plotItem.getViewBox().addItem(self._img)
        self.setCentralItem(self.plotItem)

    def setTicks(self, ticks):
        # Define and assign histogram
        self.hist = pg.HistogramLUTWidget()
        self.hist.setImageItem(self._img)
        self.hist.gradient.restoreState({"mode": "rgb", "ticks": ticks})
