#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module providing some specific items for annotation and highlight purpose.

LICENSE
    MIT License, see the LICENSE file at the root of the repository
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

# Python
import contextlib
import sys

# Linear algebra
import numpy as np

# PyQTGraph
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

# SpINY
from spiny.gui.colormaps import Ticks
from spiny.gui.items import PlayheadLine, SelectablePlotItem

###############################################################################
# Classes
###############################################################################


class CollapsibleBox(QtWidgets.QWidget):
    """A Collapsible GroupBox widget.

    This class has been adapted from a PyQt5 example
    The example is provided at this address: https://stackoverflow.com/a/52617714
    """

    def __init__(self, title: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super(CollapsibleBox, self).__init__(parent)

        self.toggle_button = QtWidgets.QToolButton(text=title, checkable=True, checked=False)
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(QtCore.Qt.RightArrow)
        self.toggle_button.pressed.connect(self.on_pressed)

        self.toggle_animation = QtCore.QParallelAnimationGroup(self)

        self.content_area = QtWidgets.QScrollArea(maximumHeight=0, minimumHeight=0)
        self.content_area.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.content_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

        self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self, b"minimumHeight"))
        self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self, b"maximumHeight"))
        self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self.content_area, b"maximumHeight"))

    def on_pressed(self) -> None:
        """Expand or collapse the box (animated)"""
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(QtCore.Qt.DownArrow if not checked else QtCore.Qt.RightArrow)
        self.toggle_animation.setDirection(
            QtCore.QAbstractAnimation.Forward if not checked else QtCore.QAbstractAnimation.Backward
        )
        self.toggle_button.setChecked(not checked)  # FIXME: seems to do the job but in a chunky way
        self.toggle_animation.start()

    def setContentLayout(self, layout: QtWidgets.QLayout) -> None:
        """Define the content of the box and the animation heights matching it

        Parameters
        ----------
        layout : QtWidgets.QLayout
            The layout to show in the box
        """
        lay = self.content_area.layout()
        del lay
        self.content_area.setLayout(layout)
        collapsed_height = self.sizeHint().height() - self.content_area.maximumHeight()
        content_height = layout.sizeHint().height()
        for i in range(self.toggle_animation.animationCount()):
            animation = self.toggle_animation.animationAt(i)
            animation.setDuration(500)
            animation.setStartValue(collapsed_height)
            animation.setEndValue(collapsed_height + content_height)

        content_animation = self.toggle_animation.animationAt(self.toggle_animation.animationCount() - 1)
        content_animation.setDuration(500)
        content_animation.setStartValue(0)
        content_animation.setEndValue(content_height)


@contextlib.contextmanager
def blocked_imports(*module_names: str) -> Iterator[None]:
    """Make the given (not yet imported) modules unimportable for the duration of the context

    pyqtgraph's gradient editor builds a colormap menu listing the colormaps of matplotlib and colorcet,
    which imports them if they are installed (about 50 MB and 0.8 s for matplotlib), only to offer them
    in a right-click menu. Blocking these imports while the editor is created avoids that cost; the
    modules can be imported normally afterwards.

    Parameters
    ----------
    module_names : list(str)
        The names of the top-level modules to block

    Yields
    ------
    None
    """
    blocked = [name for name in module_names if name not in sys.modules]
    for name in blocked:
        sys.modules[name] = None  # type: ignore[assignment]  # "import name" raises ImportError
    try:
        yield
    finally:
        for name in blocked:
            if sys.modules.get(name, 0) is None:
                del sys.modules[name]


#: The smoothing strategies of an image, by name: the weights of the filter applied along each axis (None for no filter)
SMOOTHING_KERNELS: dict[str, tuple[int, ...] | None] = {
    "None": None,
    "Bilinear": None,  # NOTE: done by the painter, when the image is drawn
    "Box": (1, 1, 1),
    "Gaussian": (1, 4, 6, 4, 1),
}


def smooth_image(image: np.ndarray, kernel: tuple[int, ...]) -> np.ndarray:
    """Filter a rendered image along its two axes

    Parameters
    ----------
    image : np.ndarray
        The image, shape (height, width) or (height, width, nb_channels), dtype uint8
    kernel : tuple(int)
        The weights of the filter, of odd length

    Returns
    -------
    np.ndarray
        The filtered image, same shape and dtype; the edges are extended
    """
    half = len(kernel) // 2
    total = sum(kernel)
    result = image.astype(np.uint16)
    for axis in (0, 1):
        padding = [(half, half) if dimension == axis else (0, 0) for dimension in range(image.ndim)]
        padded = np.pad(result, padding, mode="edge")
        length = image.shape[axis]
        result = np.zeros_like(result)
        for i, weight in enumerate(kernel):
            result += weight * padded.take(range(i, i + length), axis=axis)
        result //= total
    return result.astype(np.uint8)


class SmoothedImageItem(pg.ImageItem):
    """Image whose rendering (colours included) can be smoothed, whatever the plugin which provides the data"""

    qimage: Any

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._smoothing = "None"
        self._smoothed: np.ndarray | None = None

    def setSmoothing(self, smoothing: str) -> None:
        """Change the smoothing

        Parameters
        ----------
        smoothing : str
            The name of the strategy, a key of `SMOOTHING_KERNELS`
        """
        self._smoothing = smoothing
        self._renderRequired = True
        self.update()

    def render(self) -> None:
        """Render the image, then smooth it"""
        super().render()
        kernel = SMOOTHING_KERNELS[self._smoothing]
        if kernel is not None and self.qimage is not None:
            # NOTE: in colours, as an image with a lookup table has indices, which cannot be averaged
            colors = self.qimage.convertToFormat(QtGui.QImage.Format.Format_ARGB32)
            # NOTE: the QImage only points to the array: it has to be kept alive as long as the image is drawn
            self._smoothed = smooth_image(pg.functions.ndarray_from_qimage(colors), kernel)
            self.qimage = pg.functions.ndarray_to_qimage(self._smoothed, QtGui.QImage.Format.Format_ARGB32)

    def paint(self, painter: QtGui.QPainter, *args: Any) -> None:
        """Draw the image

        Parameters
        ----------
        painter : QtGui.QPainter
            The painter
        args : list
            The style option and widget
        """
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, self._smoothing == "Bilinear")
        super().paint(painter, *args)


class DataWidget(pg.GraphicsLayoutWidget):
    """Helper to define a Refined Data area visualisation

    The widget is composed of two items:
      - the HistogramLUTItem on top to have a refined control of the contrast
      - the SelectablePlotItem to visualise the data

    As for PlotWidget, a set of methods specific to PlotItem are accessible directly from the widget

    Only the visible part of the data is given to the image item: pg.ImageItem always renders its whole
    image (downsampled to the density of the visible area), so when zoomed in on a long recording it
    would render every frame at full resolution (hundreds of MB and seconds per frame). The displayed
    slice (a view on the data, never a copy) covers the visible range plus a margin, and is updated
    when the visible range changes.

    Attributes
    ----------
    SLICE_MARGIN : float
        The margin added on each side of the visible range, as a fraction of its width
    """

    SLICE_MARGIN = 0.5

    #: Emitted when the widget starts or stops showing data
    plottingChanged = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialisation of the widget

        It creates the histogram and the plot, and makes the most useful PlotItem methods available
        on the widget itself.

        Parameters
        ----------
        parent : QWidget
            The parent widget
        """
        super().__init__(parent, border=False)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.enableMouse(False)

        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.ci.layout.setSpacing(0)

        # A _plotItem area (ViewBox + axes) for displaying the image
        # NOTE: the frequency/dimension axis is locked, only time can be zoomed/panned
        self._plotItem = SelectablePlotItem(lock_y_axis=True)
        self._plotItem.setContentsMargins(0, 0, 0, 0)

        # Item for displaying image data: data is always given as (time, dimension), whatever the global
        # imageAxisOrder option is when the widget is created
        # NOTE: autoDownsample renders the image at screen resolution (a long recording has far more
        #       frames than pixels), so the rendered QImage stays small whatever the data size
        self._imageItem = SmoothedImageItem(axisOrder="col-major", autoDownsample=True)
        self._plotItem.addItem(self._imageItem)
        self._plotItem.addItem(PlayheadLine(), ignoreBounds=True)

        # Full data and how it is placed (see setImageData)
        self._data: np.ndarray | None = None
        self._data_transform = QtGui.QTransform()
        self._slice = (0, 0)
        self._plotItem.getViewBox().sigXRangeChanged.connect(self._updateVisibleSlice)
        self._plotItem.getViewBox().sigResized.connect(self._updateVisibleSlice)

        # Contrast/color control (see blocked_imports for why matplotlib and colorcet are blocked)
        with blocked_imports("matplotlib", "colorcet"):
            self._histItem = pg.HistogramLUTItem(orientation="horizontal")
        self._histItem.vb.setMaximumHeight(10)
        self._histItem.gradient.setMaximumHeight(10)
        self._histItem.setImageItem(self._imageItem)
        self.addItem(self._histItem)

        self.nextRow()
        self.addItem(self._plotItem)

        for m in [
            "addItem",
            "removeItem",
            "autoRange",
            "clear",
            "setAxisItems",
            "setXRange",
            "setYRange",
            "setRange",
            "setAspectLocked",
            "setMouseEnabled",
            "setXLink",
            "setYLink",
            "enableAutoRange",
            "disableAutoRange",
            "setLimits",
            "register",
            "unregister",
            "viewRect",
            "hideAxis",
            "getAxis",
            "getViewBox",
        ]:
            setattr(self, m, getattr(self._plotItem, m))

    def setMatrix(
        self,
        data: np.ndarray,
        frame_duration: float,
        y_range: tuple[float, float],
        levels: tuple[float, float] | None = None,
    ) -> None:
        """Display a (time, dimension) matrix in seconds (x) and in the given y range

        Frame i covers [i, i + 1) × frame_duration seconds and the columns are spread evenly over y_range
        (e.g. a frequency range in Hz). The view is limited to the data.

        Parameters
        ----------
        data : np.ndarray
            The matrix, shape (nb_frames, dimension). It is referenced, not copied.
        frame_duration : float
            The duration of a frame (the frameshift), in seconds
        y_range : tuple(float, float)
            The (bottom, top) values of the y axis covered by the columns
        levels : tuple(float, float), optional
            The (min, max) values mapped to the ends of the colormap, see setImageData. (default: None)
        """
        y_min, y_max = y_range
        transform = QtGui.QTransform.fromTranslate(0, y_min)
        transform.scale(frame_duration, (y_max - y_min) / max(data.shape[1], 1))  # applied before the translation
        self.setImageData(data, levels, transform)
        self._plotItem.setLimits(
            xMin=0,
            xMax=frame_duration * data.shape[0],
            yMin=y_min,
            yMax=y_max,
            minYRange=0,
            maxYRange=y_max - y_min,
        )

    def setLevels(self, levels: tuple[float, float]) -> None:
        """Change the values mapped to the ends of the colormap, without touching the data

        Parameters
        ----------
        levels : tuple(float, float)
            The (min, max) values
        """
        self._levels = levels
        self._imageItem.setLevels(levels)
        self._histItem.setLevels(*levels)

    def setYView(self, y_min: float, y_max: float) -> None:
        """Show (only) the given part of the y axis, e.g. a frequency range

        Parameters
        ----------
        y_min : float
            The bottom of the view
        y_max : float
            The top of the view
        """
        self._plotItem.setLimits(yMin=y_min, yMax=y_max, minYRange=0, maxYRange=y_max - y_min)
        self._plotItem.setYRange(y_min, y_max, padding=0)

    def setSmoothing(self, smoothing: str) -> None:
        """Smooth the image once it is rendered

        Parameters
        ----------
        smoothing : str
            The name of the strategy, a key of `SMOOTHING_KERNELS`
        """
        self._imageItem.setSmoothing(smoothing)

    def setTicks(self, ticks: Ticks) -> None:
        """Apply a colormap (it is kept when the data changes)

        Parameters
        ----------
        ticks : list(tuple(float, tuple(int, int, int, int)))
            The (position, RGBA color) gradient ticks, see spiny.gui.colormaps.colormap_ticks
        """
        self._histItem.gradient.restoreState({"mode": "rgb", "ticks": ticks})

    def setImageData(
        self,
        data: np.ndarray,
        levels: tuple[float, float] | None = None,
        transform: QtGui.QTransform | None = None,
    ) -> None:
        """Display a (time, dimension) matrix

        Parameters
        ----------
        data : np.ndarray
            The matrix, shape (nb_frames, dimension). It is referenced, not copied (a memory map works).
        levels : tuple(float, float), optional
            The (min, max) values mapped to the ends of the colormap. If None, they are estimated once
            from a subsample of the whole data (so that they do not change while panning). (default: None)
        transform : QtGui.QTransform, optional
            The transform from (frame, dimension) indices to plot coordinates (e.g. seconds x Hz).
            (default: None, i.e. the identity)
        """
        if levels is None:
            levels = self._estimateLevels(data)
        was_plotting = self.isPlotting()
        self._data = data
        self._data_transform = QtGui.QTransform(transform) if transform is not None else QtGui.QTransform()
        self._levels = levels
        self._slice = (0, 0)
        self._histItem.setLevels(*levels)
        self._updateVisibleSlice()
        if not was_plotting:
            self.plottingChanged.emit()

    @staticmethod
    def _estimateLevels(data: np.ndarray, max_values: int = 1_000_000) -> tuple[float, float]:
        """Estimate the display levels from (at most `max_values` values of) the data

        Parameters
        ----------
        data : np.ndarray
            The data, shape (nb_frames, dimension)
        max_values : int, optional
            The maximum number of values read. (default: 1000000)

        Returns
        -------
        tuple(float, float)
            The (min, max) levels
        """
        if data.size == 0:
            return (0.0, 1.0)
        step = max(1, data.shape[0] * data.shape[1] // max_values)
        sample = np.asarray(data[::step])
        low, high = float(np.nanmin(sample)), float(np.nanmax(sample))
        return (low, high) if high > low else (low, low + 1.0)

    def _visibleFrames(self) -> tuple[float, float]:
        """Return the range of frames covered by the visible x range

        Returns
        -------
        tuple(float, float)
            The (first, last) visible frames (not clipped to the data)
        """
        (x_min, x_max), _ = self._plotItem.getViewBox().viewRange()
        inverse, invertible = self._data_transform.inverted()
        if not invertible:
            return (0.0, float(0 if self._data is None else self._data.shape[0]))
        first = inverse.map(QtCore.QPointF(x_min, 0)).x()
        last = inverse.map(QtCore.QPointF(x_max, 0)).x()
        return (min(first, last), max(first, last))

    def _updateVisibleSlice(self, *args: Any) -> None:
        """Give the image item the slice of data covering the visible range (plus a margin)

        Nothing is done while the current slice still covers the visible range and is not much larger
        than it (a too large slice would make the rendering slower than needed).

        Parameters
        ----------
        args : list
            The arguments of the signal triggering the update (unused)
        """
        if self._data is None:
            return

        nb_frames = self._data.shape[0]
        first, last = self._visibleFrames()
        first, last = max(int(np.floor(first)), 0), min(int(np.ceil(last)) + 1, nb_frames)
        width = max(last - first, 1)
        current_first, current_last = self._slice
        covered = (current_first <= first) and (last <= current_last)
        if covered and (current_last - current_first) <= (1 + 4 * self.SLICE_MARGIN) * width:
            return

        margin = int(width * self.SLICE_MARGIN)
        new_first, new_last = max(first - margin, 0), min(last + margin, nb_frames)
        if new_last <= new_first:
            new_first, new_last = 0, nb_frames
        self._slice = (new_first, new_last)
        self._imageItem.setImage(self._data[new_first:new_last], autoLevels=False, levels=self._levels)

        # The slice starts at frame new_first: shift it before applying the data transform
        self._imageItem.setTransform(QtGui.QTransform.fromTranslate(new_first, 0) * self._data_transform)

    def clearImageData(self) -> None:
        """Stop displaying the data, so that its memory can be released"""
        was_plotting = self.isPlotting()
        self._data = None
        self._slice = (0, 0)
        self._imageItem.clear()
        if was_plotting:
            self.plottingChanged.emit()

    def isPlotting(self) -> bool:
        """Tell if the widget shows data

        Returns
        -------
        bool
            True if it does
        """
        return self._data is not None
