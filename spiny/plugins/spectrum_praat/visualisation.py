# PyQTGraph
from pyqtgraph.Qt import QtGui, QtWidgets

# SpINY
from spiny.gui.widgets import DataWidget


class SpectrogramPraatPlotWidget(DataWidget):
    """Plot widget rendering the spectrogram computed by Praat (parselmouth)

    Attributes
    ----------
    _spectrum_extractor : SpectrumPraatExtractor
        The extractor providing the spectrum (frames x frequency bins), the frameshift (in seconds)
        and the frequency range
    """

    def __init__(self, spectrum_extractor, parent=None, **kwargs):
        """
        Parameters
        ----------
        spectrum_extractor: SpectrumPraatExtractor
            The extractor providing the data to render

        parent: QWidget
            the parent widget
        """
        super().__init__(parent)
        color = QtWidgets.QApplication.instance().palette().color(QtGui.QPalette.Base)
        self.setBackground(color)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.enableMouse(False)

        self._spectrum_extractor = spectrum_extractor

        # NOTE: needed to conserve the colormap
        self._ticks = None

    def refresh(self):
        spectrum = self._spectrum_extractor._spectrum

        # 1. translate to the minimal frequency
        tr = QtGui.QTransform()
        min_y = self._spectrum_extractor._cutoff[0]
        tr.translate(0, min_y)

        # 2. scale (the Praat frameshift is already in seconds)
        y_scale = self._spectrum_extractor._cutoff[1] - self._spectrum_extractor._cutoff[0]
        y_scale /= spectrum.shape[1]
        tr.scale(self._spectrum_extractor._frameshift, y_scale)

        # Update the image item
        self._imageItem.setImage(spectrum)
        self._imageItem.setTransform(tr)

        # Set the limits to focus the rendering
        self._plotItem.setLimits(
            minYRange=0,
            maxYRange=min_y + spectrum.shape[1] * y_scale,
            yMin=0,
            yMax=min_y + spectrum.shape[1] * y_scale,
            xMin=0,
            xMax=self._spectrum_extractor._frameshift * spectrum.shape[0],
        )

        # Update the ticks and the histogram
        if self._ticks is not None:
            self.setTicks(self._ticks)

    def setTicks(self, ticks):
        self._ticks = ticks
        self._histItem.gradient.restoreState({"mode": "rgb", "ticks": ticks})
