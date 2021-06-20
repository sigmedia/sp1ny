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
from pyqtgraph.Qt import QtWidgets

# PyPrag
from pyprag.gui.items import *


###############################################################################
# Classes
###############################################################################


class MAPPlotWidget(pg.PlotWidget):
    """Image plot widget allowing to highlight some regions

    Attributes
    ----------
    _data : np.array
        matrix containing the data rendered

    plotItem : pyprag.gui.items.SelectablePlotItem
        The plot item contained in the widget

    hist : pg.HistogramLUTWidget
        The histogram widget to control the image colorimetrie
    """

    def __init__(
        self, data, frameshift, ticks, parent=None, background="default", **kwargs
    ):
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

        background: str
            the background of the plot

        kwargs: kwargs
            arguments passed to pg.PlotWidget

        """
        pg.GraphicsView.__init__(self, parent, background)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        self.enableMouse(False)

        # Save reference to data
        self._data = data
        self._y_scale = 16e03  # FIXME: find a way to improve this!

        # Generate image data
        img = pg.ImageItem()
        img.setImage(self._data.T)
        img.setTransform(
            QtGui.QTransform.fromScale(
                frameshift, 1.0 / (self._data.shape[1] / self._y_scale)
            )
        )

        # Define and assign histogram
        self.hist = pg.HistogramLUTWidget()
        self.hist.setImageItem(img)
        self.hist.gradient.restoreState({"mode": "rgb", "ticks": ticks})

        # Generate plot
        self.plotItem = SelectablePlotItem(**kwargs)
        self.plotItem.getViewBox().addItem(img)
        self.setCentralItem(self.plotItem)
