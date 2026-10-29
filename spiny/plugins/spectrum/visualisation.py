from __future__ import annotations

from pyqtgraph.Qt import QtWidgets

from spiny.gui.widgets import DataWidget
from .extractor import SpectrumExtractor, db_to_code


class SpectrogramPlotWidget(DataWidget):
    """Plot of the spectrogram computed by a SpectrumExtractor (seconds × Hz)

    The display range (frequencies and levels) is applied instantly, without a new analysis: the
    spectrogram stores every level down to DB_FLOOR and every frequency up to its maximum frequency.

    Parameters
    ----------
    spectrum_extractor : SpectrumExtractor
        The extractor providing the spectrogram
    parent : QtWidgets.QWidget, optional
        The parent widget. (default: None)

    Attributes
    ----------
    frequency_range : tuple(float, float)
        The displayed frequency range, in Hz
    db_range : tuple(float, float)
        The displayed level range, in dB relative to the maximum of the spectrogram
    """

    def __init__(self, spectrum_extractor: SpectrumExtractor, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._spectrum_extractor = spectrum_extractor
        self.frequency_range = (0.0, spectrum_extractor.settings.max_frequency)
        self.db_range = (-70.0, 0.0)

    def refresh(self) -> None:
        """Render the spectrogram of the extractor with the current display range"""
        extractor = self._spectrum_extractor
        frame_duration = extractor.settings.frameshift / 1000  # the frameshift is in milliseconds
        levels = (db_to_code(self.db_range[0]), db_to_code(self.db_range[1]))  # given, so the data is not scanned
        self.setMatrix(extractor._spectrum, frame_duration, (0.0, extractor._top_frequency), levels)
        self.setDisplayRange(self.frequency_range, self.db_range)

    def setDisplayRange(self, frequency_range: tuple[float, float], db_range: tuple[float, float]) -> None:
        """Show the given frequency range and map the given level range on the colormap

        Parameters
        ----------
        frequency_range : tuple(float, float)
            The (min, max) frequencies to show, in Hz (clipped to the frequencies of the spectrogram)
        db_range : tuple(float, float)
            The (min, max) levels mapped to the ends of the colormap, in dB relative to the maximum
        """
        self.frequency_range = frequency_range
        self.db_range = db_range
        top = min(frequency_range[1], self._spectrum_extractor._top_frequency)
        self.setYView(min(frequency_range[0], top), top)
        self.setLevels((db_to_code(db_range[0]), db_to_code(db_range[1])))
