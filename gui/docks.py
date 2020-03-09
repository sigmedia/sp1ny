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

from .utils import *
from .segment import *

class DockWithWav(Dock):
    def __init__(self, name, size, data, wav, frameshift, ticks, alignment=None):
        Dock.__init__(self, name=name, size=size)

        self.data = data
        self.wav = wav
        self.alignment = alignment
        max_dur = self.data.shape[0] * frameshift

        self.__plotData(frameshift, ticks)
        self.__plotWav(max_dur)
        self.__applyAlignment()

        # FIXME: temporary Refinement
        self.data_plot.getAxis('left').setStyle(showValues=False)
        self.wav_plot.getAxis('left').setStyle(showValues=False)

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

    def __plotWav(self, max_dur):
        max_point = int(max_dur * self.wav[1])
        if max_point > self.wav[0].shape[0]:
            max_point = self.wav[0].shape[0]

        wav_plot = pg.PlotWidget(name="%s waveform" % self.name)
        wav_plot.plot(x=np.linspace(0, max_dur, max_point),
                      y=self.wav[0][:max_point])

        if max_point < self.wav[0].shape[0]:
            wav_plot.plot(x=np.linspace(max_dur, self.wav[0].shape[0]/float(self.wav[1]), self.wav[0].shape[0]-max_point),
                          y=self.wav[0][max_point:], pen={'color': "F00"})
        wav_plot.setMaximumHeight(int(self.frameGeometry().height() * 20/100))

        # Add the wav plot to the dock!
        self.wav_plot = wav_plot
        self.addWidget(wav_plot)

    def __applyAlignment(self):
        if self.alignment is None:
            pass
        else:
            for i, elt in enumerate(self.alignment.reference):
                # Add boundaries
                seg = SegmentItem(elt, self.wav, showLabel=False)
                self.data_plot.addItem(seg)


class DockDiff(Dock):
    def __init__(self, name, size, data, frameshift, ticks, alignment=None):
        Dock.__init__(self, name=name, size=size)

        self.data = data
        self.alignment = alignment
        self.T = data.shape[0] * frameshift
        self.__plotData(frameshift, ticks)
        self.__plotDiffByFrame(frameshift)
        self.__applyAlignment()

        # FIXME: temporary Refinement
        self.data_plot.getAxis('left').setStyle(showValues=False)
        self.dist_plot.getAxis('left').setStyle(showValues=False)

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


    def __applyAlignment(self):
        if self.alignment is None:
            pass
        else:
            for i, elt in enumerate(self.alignment.reference):
                # Add boundaries
                seg = SegmentItem(elt, wav=None, T=self.T, showLabel=False)
                self.data_plot.addItem(seg)



class DockAlignment(Dock):
    def __init__(self, name, size, alignment, wav):
        Dock.__init__(self, name=name, size=size)

        self.alignment = alignment
        self.wav = wav
        self.__plotAlignment()

        # FIXME: temporary refinement
        for w in self.widgets:
            w.getAxis('left').setStyle(showValues=False)

    def __plotAlignment(self):
        if self.alignment is None:
            self.alignment_plot = pg.PlotWidget(name=self.name())

            # If we don't have any reference just stop here!
            if self.wav is None:
                return

            seg = SegmentItem(((0, self.wav[0].shape[0]/self.wav[1], "")), self.wav)
            self.alignment_plot.addItem(seg)
            return

        for k in self.alignment.segments:
            alignment_plot = pg.PlotWidget(name="%s_%s" % (self.name(), k))
            alignment_plot.setYRange(0, 1)
            for i, elt in enumerate(self.alignment.segments[k]):
                # Generate region item
                seg = SegmentItem(elt, self.wav)
                alignment_plot.addItem(seg)

                # Add label (FIXME: should be moved to the SegmentItem directly!)
                label = pg.TextItem(text=elt[2],anchor=(0.5,0.5))
                label.setPos((elt[1]+elt[0])/2, 0.5)

            self.addWidget(alignment_plot)

        # We need a reference plot!
        self.alignment_plot = self.widgets[-1]
        for i in range(len(self.widgets)-1):
            self.widgets[i].hideAxis('bottom')
            self.widgets[i].setXLink(self.alignment_plot)
