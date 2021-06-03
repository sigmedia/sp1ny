#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module providing some specific items for annotation and highlight purpose.

LICENSE
"""

import numpy as np
from scipy import signal
import pyqtgraph as pg

from pyprag.gui.items import *

###############################################################################
# Classes
###############################################################################

class SelectableWavPlotWidget(pg.PlotWidget):
    """Image plot widget allowing to highlight some regions

    Attributes
    ----------
    _wav : tuple(np.array, int)
        The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

    plotItem : pyprag.gui.items.SelectablePlotItem
        The plot item contained in the widget

    """
    def __init__(self, wav, max_dur, parent=None, background='default', **kwargs):
        """
        Parameters
        ----------
        wav : tuple(np.array, int)
            The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.
        max_dur: float
            Maximum duration considered as valid. Remaining part will be plot using a different pen (red)

        ticks: TODO
            color map ticks

        parent: pg.GraphicsObject
            the parent object

        background: str
            the background of the plot

        kwargs: kwargs
            arguments passed to pg.PlotWidget

        """
        super().__init__(parent=parent, background=background)

        # Save reference to wav
        self._wav = wav
        x = np.arange(self._wav[0].shape[0]) / self._wav[1]

        # Prepare plot item
        self.plotItem = SelectablePlotItem(**kwargs)
        self.setCentralItem(self.plotItem)
        self.plotItem.plot(x, self._wav[0])


class SelectableImagePlotWidget(pg.PlotWidget):
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

    def __init__(self, data, frameshift, ticks, y_scale, parent=None, background='default', **kwargs):
        """
        Parameters
        ----------
        data: np.array
            matrix containing the data to render

        frameshift: float
            frameshift in senconds

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
        self._y_scale = y_scale

        # Generate image data
        img = pg.ImageItem()
        img.setImage(self._data.T)
        img.setTransform(QtGui.QTransform.fromScale(frameshift, 1.0/(self._data.shape[1]/self._y_scale)))

        # Define and assign histogram
        self.hist = pg.HistogramLUTWidget()
        self.hist.setImageItem(img)
        self.hist.gradient.restoreState(
            {'mode': 'rgb', 'ticks': ticks}
        )

        # Generate plot
        self.plotItem = SelectablePlotItem(**kwargs)
        self.plotItem.getViewBox().addItem(img)
        self.setCentralItem(self.plotItem)


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

    def __init__(self, data, frameshift, ticks, parent=None, background='default', **kwargs):
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
        self._y_scale = 16e03 # FIXME: find a way to improve this!

        # Generate image data
        img = pg.ImageItem()
        img.setImage(self._data.T)
        img.setTransform(QtGui.QTransform.fromScale(frameshift, 1.0/(self._data.shape[1]/self._y_scale)))

        # Define and assign histogram
        self.hist = pg.HistogramLUTWidget()
        self.hist.setImageItem(img)
        self.hist.gradient.restoreState(
            {'mode': 'rgb', 'ticks': ticks}
        )

        # Generate plot
        self.plotItem = SelectablePlotItem(**kwargs)
        self.plotItem.getViewBox().addItem(img)
        self.setCentralItem(self.plotItem)
