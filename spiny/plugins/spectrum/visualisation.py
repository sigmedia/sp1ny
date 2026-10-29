from __future__ import annotations

from pyqtgraph.Qt import QtWidgets

from spiny.gui.widgets import DataWidget
from .extractor import SpectrumExtractor


class SpectrogramPlotWidget(DataWidget):
    """Plot of the spectrogram computed by a SpectrumExtractor (seconds × Hz)

    Parameters
    ----------
    spectrum_extractor : SpectrumExtractor
        The extractor providing the spectrogram
    parent : QtWidgets.QWidget, optional
        The parent widget. (default: None)
    """

    def __init__(self, spectrum_extractor: SpectrumExtractor, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._spectrum_extractor = spectrum_extractor

    def refresh(self) -> None:
        """Render the spectrogram of the extractor"""
        extractor = self._spectrum_extractor
        frame_duration = extractor._frameshift / 1000  # the frameshift is in milliseconds
        self.setMatrix(extractor._spectrum, frame_duration, extractor._cutoff, levels=(0, 255))  # 8-bit codes
