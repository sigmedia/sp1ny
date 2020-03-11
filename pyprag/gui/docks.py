#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

LICENSE
    This script is in the public domain, free from copyrights or restrictions.
    Created:  6 March 2020
"""

# Linear algebra
import numpy as np

# Plotting
import matplotlib.cm
from pyqtgraph.dockarea import *
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

from pyprag.gui.utils import *
from pyprag.gui.items import *
from pyprag.gui.widgets import *

class DockWithWav(Dock):
    def __init__(self, name, size, data, wav, frameshift, ticks):
        Dock.__init__(self, name=name, size=size)

        self.data = data
        self.wav = wav
        max_dur = self.data.shape[0] * frameshift

        self.__plotData(frameshift, ticks)
        self.__plotWav(max_dur)

        # Label space
        self.data_plot.getAxis('left').setWidth(50)
        self.wav_plot.getAxis('left').setWidth(50)

        # Reactivate autorange
        self.data_plot.autoRange()

    def __plotData(self, frameshift, ticks, y_scale=16e3):  # FIXME: y_scale is non sense for now!
        lim_factor = 1.1
        self.data_plot = SelectableImagePlotWidget(self.data, frameshift, ticks,
                                                   name="%s coef" % self.name,
                                                   wav=self.wav)
        self.data_plot.setLimits(xMax=self.data.shape[0]*frameshift*lim_factor)
        self.data_plot.hideAxis('bottom')

        # Add plot
        self.data_plot.disableAutoRange()
        self.addWidget(self.data_plot)

    def __plotWav(self, max_dur):
        lim_factor = 1.1
        self.wav_plot = SelectableWavPlotWidget(self.wav, max_dur, name="%s waveform" % self.name)
        self.wav_plot.setLimits(xMax=max_dur*lim_factor)
        self.wav_plot.setMaximumHeight(int(self.frameGeometry().height() * 20/100))
        self.addWidget(self.wav_plot)


class DockDiff(Dock):
    def __init__(self, name, size, data, frameshift, ticks):
        Dock.__init__(self, name=name, size=size)

        self.data = data
        self.T = data.shape[0] * frameshift
        self.__plotData(frameshift, ticks)
        self.__plotDiffByFrame(frameshift)

        # FIXME: temporary Refinement
        self.data_plot.getAxis('left').setLabel("Difference map")
        self.data_plot.getAxis('left').setWidth(50)
        self.dist_plot.getAxis('left').setLabel("Difference by frame")
        self.dist_plot.getAxis('left').setWidth(50)

    def __plotData(self, frameshift, ticks, y_scale=16e3):  # FIXME: y_scale is non sense for now!
        # Generate image data
        img = pg.ImageItem()
        img.setImage(self.data.T)
        img.scale(frameshift, 1.0/(self.data.shape[1]/y_scale))

        # Define and assign histogram
        hist = pg.HistogramLUTWidget()
        hist.setImageItem(img)
        hist.gradient.restoreState(
            {'mode': 'rgb', 'ticks': ticks}
        )

        # Generate plot
        plot = pg.PlotWidget(name="%s coef" % self.name)
        plot.addItem(img)
        plot.hideAxis('bottom')

        # Add plot
        self.data_plot = plot
        self.addWidget(plot)

    def __plotDiffByFrame(self, frameshift):

        data_per_frame = np.mean(self.data, axis=1)

        # - Generate color map
        pos, rgba_colors = zip(*cmapToColormap(matplotlib.cm.jet, alpha=150))
        cmap =  pg.ColorMap(pos, rgba_colors)
        lut = cmap.getLookupTable(0.0, 1.0, 10)
        ticks = list(enumerate(lut))

        # - Generate gradient
        grad = QtGui.QLinearGradient(0, 0, 0, np.max(data_per_frame))
        for i in range(len(ticks)):
            grad.setColorAt(ticks[i][0]/ticks[-1][0], pg.mkColor(ticks[i][1]))
        brush = QtGui.QBrush(grad)

        # - Generate plot
        dist_plot = pg.PlotWidget(name="Distance per frame")
        pc = pg.PlotCurveItem(x=np.linspace(0, data_per_frame.shape[0]*frameshift, data_per_frame.shape[0]),
                              y=data_per_frame,  brush=brush, fillLevel=0, pen=None)
        dist_plot.addItem(pc)
        # dist_plot.plot(x=np.linspace(0, data_per_frame.shape[0]*x_scale, data_per_frame.shape[0]),
        #                y=data_per_frame, brush=brush)
        dist_plot.setMaximumHeight(70)

        # Add plot to dock!
        self.dist_plot = dist_plot
        self.addWidget(dist_plot)


class DockAlignment(Dock):
    def __init__(self, name, size, alignment, wav):
        Dock.__init__(self, name=name, size=size)

        self.segments = []
        self.alignment = alignment
        self.wav = wav

        self.__plotAlignment()

        # FIXME: temporary refinement
        for w in self.widgets:
            w.getAxis('left').setWidth(50)
            w.getAxis('left').setStyle(showValues=False)
            w.autoRange()

    def __plotAlignment(self):
        lim_factor = 1.1
        T_max = self.wav[0].shape[0]/self.wav[1]
        for k in self.alignment.segments:
            reference_plot = pg.PlotWidget(name="%s_%s" % (self.name(), k))
            reference_plot.disableAutoRange()
            reference_plot.getAxis("left").setLabel(k)
            reference_plot.setYRange(0, 1)
            for i, elt in enumerate(self.alignment.segments[k]):
                # Generate region item
                seg = AnnotationItem(elt, self.wav)
                reference_plot.addItem(seg)


            if T_max < self.alignment.segments[k][-1][1]:
                T_max = self.alignment.segments[k][-1][1]

            self.addWidget(reference_plot)

        # We need a reference plot!
        self.reference_plot = self.widgets[-1]
        self.reference_plot.setLimits(xMax=T_max*lim_factor)
        for i in range(len(self.widgets)-1):
            self.widgets[i].hideAxis('bottom')
            self.widgets[i].setXLink(self.reference_plot)
            self.widgets[i].setLimits(xMax=T_max*lim_factor)
