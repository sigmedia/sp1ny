#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module providing some specific items for annotation and highlight purpose.

LICENSE
"""
# Python
import numpy as np

# PyQTGraph
import pyqtgraph as pg
from pyqtgraph.dockarea import Dock

# PyPrag
from pyprag.gui.items import SelectablePlotItem
from .player import player

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

    def __init__(self, wav, parent=None, background="default", **kwargs):
        """
        Parameters
        ----------
        wav : tuple(np.array, int)
            The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.
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
        self.plotItem = SelectablePlotItem(lock_y_axis=True, **kwargs)
        self.setCentralItem(self.plotItem)
        self.plotItem.plot(x, self._wav[0])
        self.plotItem.setXRange(0, self._wav[0].shape[0] / self._wav[1], padding=0)
        v_bar = pg.InfiniteLine(pos=0, movable=False, angle=90, pen=pg.mkPen({"color": "#F00", "width": 2}))

        def _update_position_handler(position):
            v_bar.setValue(position)

        player.add_position_handler(_update_position_handler)
        self.plotItem.addItem(v_bar)


class WavDock(Dock):
    """Dock containing a data surface plot (matrix data for now) and the corresponding waveform

    Attributes
    ----------
    data : np.array
        matrix containing the data to render

    wav : tuple(np.array, int)
        The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

    data_plot :
        The plot item rendering the data part

    wav_plot :
        The plot item rendering the waveform
    """

    def __init__(self, name, size, wav):
        """
        Parameters
        ----------
        name : string
            The name of the dock

        size : TODO
            The size of the widget

        data : np.array
            The data to render

        wav : tuple(np.array, int)
            The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

        frameshift : float
            The frameshift used to extract the data from the signal

        ticks : TODO
            The color map ticks

        """
        Dock.__init__(self, name=name, size=size)

        self.wav = wav

        self.__plotWav()

        # Label space
        self.wav_plot.getAxis("left").setWidth(50)

    def __plotWav(self):
        """Helper to plot the waveform

        Parameters
        ----------
        max_dur : float
          The maximum duration in seconds. It is mainly used in the case
          that the annotations require more space than the waveform
        """

        self.wav_plot = SelectableWavPlotWidget(self.wav, name="%s waveform" % self.name)
        self.addWidget(self.wav_plot)
