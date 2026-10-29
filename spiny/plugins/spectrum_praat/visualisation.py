from __future__ import annotations

from pyqtgraph.Qt import QtWidgets

from spiny.gui.widgets import DataWidget
from .extractor import SpectrumPraatExtractor


class SpectrogramPraatPlotWidget(DataWidget):
    """Plot of the spectrogram computed by Praat (seconds × Hz)

    Parameters
    ----------
    spectrum_extractor : SpectrumPraatExtractor
        The extractor providing the spectrogram
    parent : QtWidgets.QWidget, optional
        The parent widget. (default: None)
    """

    def __init__(self, spectrum_extractor: SpectrumPraatExtractor, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._spectrum_extractor = spectrum_extractor

    def refresh(self) -> None:
        """Render the spectrogram of the extractor"""
        extractor = self._spectrum_extractor
        # NOTE: Praat gives the frameshift in seconds already
        self.setMatrix(extractor._spectrum, extractor._frameshift, extractor._cutoff, levels=(0, 255))  # 8-bit codes
