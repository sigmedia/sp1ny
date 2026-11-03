from __future__ import annotations

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from spiny.core import player
from spiny.gui.widgets import DataWidget
from .extractor import DEFAULT_DB_RANGE, SpectrumExtractor, db_to_code


class SpectrogramPlotWidget(DataWidget):
    """Plot of the spectrogram computed by a SpectrumExtractor (seconds × Hz)

    The display range (frequencies and levels) is applied instantly, without a new analysis: the
    spectrogram stores every level down to DB_FLOOR and every frequency up to its maximum frequency.
    A message can be shown over the plot, e.g. to explain why there is no spectrogram.

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
        The displayed level range, in dB (see DB_FLOOR)
    """

    def __init__(self, spectrum_extractor: SpectrumExtractor, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._spectrum_extractor = spectrum_extractor
        self.frequency_range = (0.0, spectrum_extractor.settings.max_frequency)
        self.db_range = DEFAULT_DB_RANGE

        self._message = QtWidgets.QLabel()
        self._message.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        # The label covers the whole widget: the mouse must still reach the plot, to zoom in
        self._message.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        QtWidgets.QVBoxLayout(self).addWidget(self._message)

    def refresh(self) -> None:
        """Render the current spectrogram of the extractor (if any) with the current display range"""
        spectrogram = self._spectrum_extractor.spectrogram
        # The spectrogram may only cover a part of the signal, the view must still be able to reach all of it
        self._plotItem.setLimits(xMin=0, xMax=player.duration)
        if spectrogram is None:
            self.clearImageData()
        else:
            transform = QtGui.QTransform.fromTranslate(spectrogram.start_time, 0)
            bin_height = spectrogram.top_frequency / spectrogram.codes.shape[1]
            transform.scale(spectrogram.frame_duration, bin_height)  # applied before the translation
            self.setImageData(
                spectrogram.codes, (db_to_code(self.db_range[0]), db_to_code(self.db_range[1])), transform
            )
        self.setDisplayRange(self.frequency_range, self.db_range)

    def setMessage(self, text: str) -> None:
        """Show a message over the plot

        Parameters
        ----------
        text : str
            The message, empty to remove it
        """
        self._message.setText(text)

    def setDisplayRange(self, frequency_range: tuple[float, float], db_range: tuple[float, float]) -> None:
        """Show the given frequency range and map the given level range on the colormap

        Parameters
        ----------
        frequency_range : tuple(float, float)
            The (min, max) frequencies to show, in Hz (clipped to the frequencies of the spectrogram)
        db_range : tuple(float, float)
            The (min, max) levels mapped to the ends of the colormap, in dB (see DB_FLOOR)
        """
        self.frequency_range = frequency_range
        self.db_range = db_range
        spectrogram = self._spectrum_extractor.spectrogram
        top = frequency_range[1] if spectrogram is None else min(frequency_range[1], spectrogram.top_frequency)
        self.setYView(min(frequency_range[0], top), top)
        self.setLevels((db_to_code(db_range[0]), db_to_code(db_range[1])))
