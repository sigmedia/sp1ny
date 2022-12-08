# PyQTGraph
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui

# PyPrag
from pyprag.gui.items import SelectablePlotItem


class SpectrogramPlotWidget(pg.PlotWidget):
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

    def __init__(self, spectrum_extractor, parent=None, background="default", **kwargs):
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

        self._spectrum_extractor = spectrum_extractor

    def refresh(self):
        self._img = pg.ImageItem()
        self._img.setImage(self._spectrum_extractor._spectrum.T)

        # 1. translate to the minimal frequency
        min_y = self._spectrum_extractor._cutoff[0]
        self._img.translate(0, min_y)

        # 2. scale
        y_scale = self._spectrum_extractor._cutoff[1] - self._spectrum_extractor._cutoff[0]
        y_scale /= self._spectrum_extractor._spectrum.shape[1]
        self._img.scale(self._spectrum_extractor._frameshift, y_scale)

        # Generate plot
        self.plotItem = SelectablePlotItem()
        self.plotItem.getViewBox().addItem(self._img)
        self.setCentralItem(self.plotItem)

    def setTicks(self, ticks):
        # Define and assign histogram
        self.hist = pg.HistogramLUTWidget()
        self.hist.setImageItem(self._img)
        self.hist.gradient.restoreState({"mode": "rgb", "ticks": ticks})
