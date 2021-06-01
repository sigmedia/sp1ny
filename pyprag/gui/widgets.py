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
    def __init__(self, wav, max_dur, parent=None, background='sdefault', step=2, **kwargs):
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
        pg.GraphicsView.__init__(self, parent, background)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        self.enableMouse(False)

        # Save reference to wav
        self._wav = wav

        # Prepare plot item
        self.plotItem = SelectablePlotItem(**kwargs)
        self.setCentralItem(self.plotItem)

        # Compute maximum point
        max_point = int(max_dur * self._wav[1])
        if max_point > self._wav[0].shape[0]:
            max_point = self._wav[0].shape[0]

        self.step = step  # FIXME: hardcoded

        # Plot wave form until max_dur
        self.plotItem.plot(x=np.arange(0, max_point, self.step)*max_dur/max_point,
                           y=self._wav[0][0:max_point:self.step])

        # #  Plot remaing sample
        # if max_point < self._wav[0].shape[0]:
        #     self.plotItem.plot(x=np.arange(max_point, self._wav[0].shape[0], self.step)*max_dur/max_point,
        #                        y=self._wav[0][max_point:-1:self.step],
        #                        pen={'color': "F00"})

        ## Explicitly wrap methods from plotItem
        ## NOTE: If you change this list, update the documentation above as well.
        for m in ['addItem', 'removeItem', 'autoRange', 'clear', 'setXRange',
                  'setYRange', 'setRange', 'setAspectLocked', 'setMouseEnabled',
                  'setXLink', 'setYLink', 'enableAutoRange', 'disableAutoRange',
                  'setLimits', 'register', 'unregister', 'viewRect']:
            setattr(self, m, getattr(self.plotItem, m))

        self.plotItem.sigRangeChanged.connect(self.viewRangeChanged)


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

    def __init__(self, data, frameshift, ticks, parent=None, background='default', **kwargs):
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
        self._y_scale = 16e03 # FIXME: find a way to improve this!

        # Generate image data
        img = pg.ImageItem()
        img.setImage(self._data.T)
        img.scale(frameshift, 1.0/(self._data.shape[1]/self._y_scale))

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

        ## Explicitly wrap methods from plotItem
        ## NOTE: If you change this list, update the documentation above as well.
        for m in ['addItem', 'removeItem', 'autoRange', 'clear', 'setXRange',
                  'setYRange', 'setRange', 'setAspectLocked', 'setMouseEnabled',
                  'setXLink', 'setYLink', 'enableAutoRange', 'disableAutoRange',
                  'setLimits', 'register', 'unregister', 'viewRect']:
            setattr(self, m, getattr(self.plotItem, m))

        self.plotItem.sigRangeChanged.connect(self.viewRangeChanged)


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
        img.scale(frameshift, 1.0/(self._data.shape[1]/self._y_scale))

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
