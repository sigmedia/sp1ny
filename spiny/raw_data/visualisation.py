from __future__ import annotations

from pyqtgraph.Qt import QtWidgets

from spiny.gui.widgets import DataWidget
from .extractor import RawDataExtractor


class RawDataPlotWidget(DataWidget):
    """Plot of raw coefficients (seconds × coefficient index)

    Parameters
    ----------
    data_extractor : RawDataExtractor
        The loader providing the coefficients
    parent : QtWidgets.QWidget, optional
        The parent widget. (default: None)
    """

    def __init__(self, data_extractor: RawDataExtractor, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._data_extractor = data_extractor

    def refresh(self) -> None:
        """Render the coefficients of the extractor (the display levels are estimated from the data)"""
        data = self._data_extractor._data
        frame_duration = self._data_extractor._frameshift / 1000  # the frameshift is in milliseconds
        self.setMatrix(data, frame_duration, (0, data.shape[1]))
