from __future__ import annotations

from typing import Any

# Python
import numpy as np

# PyQTGraph
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from pyqtgraph.dockarea import Dock

# SpINY
from spiny.gui.items import PlayheadLine, SelectablePlotItem
from .player import player

###############################################################################
# Classes
###############################################################################


class WaveformItem(pg.GraphicsObject):
    """Graphics item drawing a (long) signal at screen resolution

    Instead of building a path with one point per sample (one float64 time value per sample plus a
    QPainterPath of the same size), the item only draws what is visible:

    - when zoomed in (at most `RAW_SAMPLES_PER_PIXEL` samples per pixel), the visible samples are
      drawn as a polyline;
    - otherwise one vertical min/max segment is drawn per pixel column, computed from the coarsest
      level of a min/max pyramid which is still finer than a pixel.

    The pyramid costs about 3% of the signal memory, and painting costs O(pixels) whatever the length
    of the signal.

    Parameters
    ----------
    pen : QPen or color, optional
        The pen used to draw the signal (any argument accepted by pg.mkPen). (default: None)

    Attributes
    ----------
    RAW_SAMPLES_PER_PIXEL : float
        Up to this density, the samples themselves are drawn
    PYRAMID_FACTORS : tuple(int)
        The number of samples summarised by one element of each pyramid level
    """

    RAW_SAMPLES_PER_PIXEL = 2.0
    PYRAMID_FACTORS = (64, 1024, 16384)

    def __init__(self, pen: Any = None) -> None:
        super().__init__()
        self._pen = pg.mkPen(pen)
        self._signal = np.zeros(0, dtype=np.float32)
        self._sampling_rate = 1
        self._levels: list[tuple[int, np.ndarray, np.ndarray]] = []  # (factor, mins, maxs), finest first
        self._y_range = (-1.0, 1.0)
        self._path = QtGui.QPainterPath()
        self._path_key: tuple[int, int, int] | None = None  # What self._path shows: (first, last, nb_columns)

    def setSignal(self, signal: np.ndarray, sampling_rate: int) -> None:
        """Define the signal to draw and (re)build its min/max pyramid

        Parameters
        ----------
        signal : np.ndarray
            The mono signal, shape (nb_samples,). It is referenced, not copied.
        sampling_rate : int
            The sampling rate, used to place the samples in seconds
        """
        self.prepareGeometryChange()
        self._signal = signal
        self._sampling_rate = sampling_rate
        self._levels = []
        self._path_key = None

        # Each level summarises `factor` samples by their minimum and maximum
        mins = maxs = signal
        previous_factor = 1
        for factor in self.PYRAMID_FACTORS:
            step = factor // previous_factor
            nb_blocks = mins.shape[0] // step
            if nb_blocks < 2:
                break
            mins = mins[: nb_blocks * step].reshape(nb_blocks, step).min(axis=1)
            maxs = maxs[: nb_blocks * step].reshape(nb_blocks, step).max(axis=1)
            self._levels.append((factor, mins, maxs))
            previous_factor = factor

        if signal.size > 0:
            source = self._levels[-1] if self._levels else (1, signal, signal)
            self._y_range = (float(min(source[1].min(), signal[-1])), float(max(source[2].max(), signal[-1])))
        self.update()

    def boundingRect(self) -> QtCore.QRectF:
        """Return the area covered by the signal (in seconds x amplitude)

        Returns
        -------
        QtCore.QRectF
            The bounding rectangle
        """
        y_min, y_max = self._y_range
        return QtCore.QRectF(0.0, y_min, self._signal.shape[0] / self._sampling_rate, max(y_max - y_min, 1e-6))

    def dataBounds(
        self, axis: int, frac: float = 1.0, orthoRange: tuple[float, float] | None = None
    ) -> tuple[float, float]:
        """Return the data range along one axis (used by pyqtgraph to auto-range the view)

        Parameters
        ----------
        axis : int
            0 for x (time), 1 for y (amplitude)
        frac : float, optional
            Ignored: the full range is always returned
        orthoRange : tuple, optional
            Ignored

        Returns
        -------
        tuple(float, float)
            The (min, max) range
        """
        if axis == 0:
            return (0.0, self._signal.shape[0] / self._sampling_rate)
        return self._y_range

    def viewRangeChanged(self) -> None:
        """Redraw when the visible range changes (the drawn resolution depends on it)"""
        self.update()

    def _visibleEnvelope(self, first: int, last: int, nb_columns: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute the per-column minimum and maximum of the samples [first, last)

        Parameters
        ----------
        first : int
            The first visible sample
        last : int
            The sample after the last visible one
        nb_columns : int
            The number of pixel columns

        Returns
        -------
        positions : np.ndarray
            The first sample of each column
        mins : np.ndarray
            The minimum of each column
        maxs : np.ndarray
            The maximum of each column
        """
        samples_per_column = (last - first) / nb_columns

        # Coarsest level which still has at least one element per column
        factor, mins, maxs = 1, self._signal, self._signal
        for level in self._levels:
            if level[0] > samples_per_column:
                break
            factor, mins, maxs = level

        start, stop = first // factor, min(-(-last // factor), mins.shape[0])
        boundaries = np.unique(
            (start + np.arange(nb_columns) * (samples_per_column / factor)).astype(np.intp).clip(start, stop - 1)
        )
        local = boundaries - start
        col_mins = np.minimum.reduceat(mins[start:stop], local)
        col_maxs = np.maximum.reduceat(maxs[start:stop], local)

        # The pyramid levels do not cover the last (incomplete) block of the signal: add it from the samples
        covered = mins.shape[0] * factor
        if last > covered:
            tail = self._signal[max(covered, first) : last]
            col_mins[-1] = min(col_mins[-1], tail.min())
            col_maxs[-1] = max(col_maxs[-1], tail.max())
        return boundaries * factor, col_mins, col_maxs

    def paint(self, painter: QtGui.QPainter, *args: Any) -> None:
        """Draw the visible part of the signal at the current screen resolution

        Parameters
        ----------
        painter : QtGui.QPainter
            The painter
        args : list
            The style option and widget (unused)
        """
        view = self.getViewBox()
        nb_samples = self._signal.shape[0]
        if view is None or nb_samples < 2:
            return

        (x_min, x_max), _ = view.viewRange()
        first = max(int(np.floor(x_min * self._sampling_rate)), 0)
        last = min(int(np.ceil(x_max * self._sampling_rate)) + 1, nb_samples)
        nb_columns = max(int(view.width()), 1)
        if last - first < 2:
            return

        # The playhead repaints the plot at every move, while what is drawn here only depends on the view
        key = (first, last, nb_columns)
        if key != self._path_key:
            self._path = self._buildPath(first, last, nb_columns)
            self._path_key = key

        painter.setPen(self._pen)
        painter.drawPath(self._path)

    def _buildPath(self, first: int, last: int, nb_columns: int) -> QtGui.QPainterPath:
        """Build the path of the samples [first, last) for the given number of pixel columns

        Parameters
        ----------
        first : int
            The first visible sample
        last : int
            The sample after the last visible one
        nb_columns : int
            The number of pixel columns

        Returns
        -------
        QtGui.QPainterPath
            The path, in seconds x amplitude
        """
        if (last - first) / nb_columns <= self.RAW_SAMPLES_PER_PIXEL:
            x = np.arange(first, last) / self._sampling_rate
            return pg.arrayToQPath(x, self._signal[first:last], connect="all")

        _, mins, maxs = self._visibleEnvelope(first, last, nb_columns)
        # Draw each segment at the centre of its pixel column: evenly spaced, so no pixel column stays empty
        centres = first + (np.arange(mins.shape[0]) + 0.5) * (last - first) / nb_columns
        x = np.repeat(centres / self._sampling_rate, 2)
        y = np.stack([mins, maxs], axis=1).ravel()
        return pg.arrayToQPath(x, y, connect="pairs")


class WavPlotWidget(pg.PlotWidget):
    """Waveform plot of the signal loaded in the player, with region selection and a playback cursor

    Attributes
    ----------
    plotItem : spiny.gui.items.SelectablePlotItem
        The plot item contained in the widget
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None, **kwargs: Any) -> None:
        """
        Parameters
        ----------
        parent: QWidget
            the parent widget

        kwargs: kwargs
            arguments passed to spiny.gui.items.SelectablePlotItem
        """
        # NOTE: given to the constructor, because PlotWidget binds its setXRange, setLimits, ... to this item
        super().__init__(parent=parent, plotItem=SelectablePlotItem(lock_y_axis=True, default_padding=0, **kwargs))

        color = QtWidgets.QApplication.instance().palette().color(QtGui.QPalette.Text)
        self._waveform = WaveformItem(pen=color)
        self.plotItem.addItem(self._waveform)
        self.refresh()

        self.plotItem.addItem(PlayheadLine(), ignoreBounds=True)

    def refresh(self) -> None:
        """(Re)draw the waveform of the signal currently loaded in the player"""
        self._waveform.setSignal(player.signal[:, 0], player.sampling_rate)

        # Define the limits to constraint the zoom
        T = player.duration
        self.plotItem.setLimits(
            yMin=-1,
            yMax=1,
            xMin=0,
            xMax=T,
            minXRange=0,
            maxXRange=T,
        )
        self.plotItem.setXRange(0, T, padding=0)


class WavDock(Dock):
    """Dock containing the waveform of the signal loaded in the player

    Attributes
    ----------
    wav_plot : WavPlotWidget
        The widget rendering the waveform
    """

    def __init__(self, name: str, size: tuple[int, int]) -> None:
        """
        Parameters
        ----------
        name : string
            The name of the dock

        size : tuple(int, int)
            The default size of the dock
        """
        Dock.__init__(self, name=name, size=size)
        self.__plotWav()

        # Label space
        self.wav_plot.getAxis("left").setWidth(50)

    def __plotWav(self) -> None:
        """Helper to create the waveform widget"""
        self.wav_plot = WavPlotWidget(name="%s waveform" % self.name)
        self.addWidget(self.wav_plot)
