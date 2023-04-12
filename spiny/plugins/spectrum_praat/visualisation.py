# PyQTGraph
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtWidgets

# PyPrag
from spiny.gui.items import SelectablePlotItem


class SpectrogramPraatPlotWidget(pg.PlotWidget):
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

        self._spectrum_extractor = spectrum_extractor

        # NOTE: needed to conserve the colormap
        self._ticks = None

    def refresh(self):
        self._img = pg.ImageItem()
        self._img.setImage(self._spectrum_extractor._spectrum.T)

        # 1. translate to the minimal frequency
        tr = QtGui.QTransform()
        min_y = self._spectrum_extractor._cutoff[0]
        tr.translate(0, min_y)

        # 2. scale
        y_scale = self._spectrum_extractor._cutoff[1] - self._spectrum_extractor._cutoff[0]
        y_scale /= self._spectrum_extractor._spectrum.shape[1]
        tr.scale(self._spectrum_extractor._frameshift, y_scale)

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
