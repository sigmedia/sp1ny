#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module providing some specific items for annotation and highlight purpose.

LICENSE
"""

# PyQTGraph
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtGui, QtCore

# SpINY
from spiny.gui.items import SelectablePlotItem


###############################################################################
# Classes
###############################################################################


class MAPPlotWidget(pg.PlotWidget):
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

    def __init__(self, data, frameshift, ticks, parent=None, **kwargs):
        """
        Parameters
        ----------
        data: np.array
            matrix containing the data to render

        frameshift: float
            frameshift in seconds

        ticks: TODO
            color map ticks

        parent: pg.GraphicsObject
            the parent object

        kwargs: kwargs
            arguments passed to pg.PlotWidget

        """
        pg.GraphicsView.__init__(self, parent)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        self.enableMouse(False)

        # Save reference to data
        self._data = data
        self._y_scale = 16e03  # FIXME: find a way to improve this!

        # Generate image data
        img = pg.ImageItem()
        img.setImage(self._data.T)
        img.setTransform(QtGui.QTransform.fromScale(frameshift, 1.0 / (self._data.shape[1] / self._y_scale)))

        # Define and assign histogram
        self.hist = pg.HistogramLUTWidget()
        self.hist.setImageItem(img)
        self.hist.gradient.restoreState({"mode": "rgb", "ticks": ticks})

        # Generate plot
        self.plotItem = SelectablePlotItem(**kwargs)
        self.plotItem.getViewBox().addItem(img)
        self.setCentralItem(self.plotItem)


class CollapsibleBox(QtWidgets.QWidget):
    """A Collapsible GroupBox widget.

    This class has been adapted from a PyQt5 example
    The example is provided at this address: https://stackoverflow.com/a/52617714
    """

    def __init__(self, title="", parent=None):
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

    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(QtCore.Qt.DownArrow if not checked else QtCore.Qt.RightArrow)
        self.toggle_animation.setDirection(
            QtCore.QAbstractAnimation.Forward if not checked else QtCore.QAbstractAnimation.Backward
        )
        self.toggle_button.setChecked(not checked)  # FIXME: seems to do the job but in a chunky way
        self.toggle_animation.start()

    def setContentLayout(self, layout):
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


class DataWidget(pg.GraphicsLayoutWidget):
    """Helper to define a Refined Data area visualisation

    The widget is composed of two items:
      - the HistogramLUTItem on top to have a refined control of the contrast
      - the SelectablePlotItem to visualise the data

    As for PlotWidget, a set of methods specific to PlotItem are accessible directly from the widget
    """

    def __init__(self, parent=None) -> None:
        """Initialisation of the widget

        It creates place holders for the two items and hook the
        methods to the plotItem

        Parameters
        ----------
        parent : QWidget
            The parent widget
        """
        super().__init__(parent, border=False)

        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.ci.layout.setSpacing(0)

        # A _plotItem area (ViewBox + axes) for displaying the image
        self._plotItem = SelectablePlotItem()
        self._plotItem.setContentsMargins(0, 0, 0, 0)

        # Item for displaying image data
        self._imageItem = pg.ImageItem()
        self._plotItem.addItem(self._imageItem)

        # Contrast/color control
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
        ]:
            setattr(self, m, getattr(self._plotItem, m))
