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


class DockWithWav(Dock):
    def __init__(self, name, size, coef, wav, frameshift, ticks, alignment=None):
        Dock.__init__(self, name=name, size=size)

        max_dur = coef.shape[0] * frameshift

        self.__plotData(coef, frameshift, ticks)
        self.__plotWav(wav, max_dur)
        self.__applyAlignment(alignment)

        # FIXME: temporary Refinement
        self.data_plot.getAxis('left').setStyle(showValues=False)
        self.wav_plot.getAxis('left').setStyle(showValues=False)

    def __plotData(self, data, frameshift, ticks, y_scale=16e3):  # FIXME: y_scale is non sense for now!
        # Generate image data
        img = pg.ImageItem()
        img.setImage(data.T)
        img.scale(frameshift, 1.0/(data.shape[1]/y_scale))

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

    def __plotWav(self, wav_data, max_dur):
        max_point = int(max_dur * wav_data[1])
        if max_point > wav_data[0].shape[0]:
            max_point = wav_data[0].shape[0]

        wav_plot = pg.PlotWidget(name="%s waveform" % self.name)
        wav_plot.plot(x=np.linspace(0, max_dur, max_point),
                      y=wav_data[0][:max_point])

        if max_point < wav_data[0].shape[0]:
            wav_plot.plot(x=np.linspace(max_dur, wav_data[0].shape[0]/float(wav_data[1]), wav_data[0].shape[0]-max_point),
                          y=wav_data[0][max_point:], pen={'color': "F00"})
        wav_plot.setMaximumHeight(int(self.frameGeometry().height() * 20/100))

        # Add the wav plot to the dock!
        self.wav_plot = wav_plot
        self.addWidget(wav_plot)

    def __applyAlignment(self, alignment):
        for p in self.widgets:
            for i, elt in enumerate(alignment):
                # Add boundaries
                seg = pg.LinearRegionItem(movable=False)
                seg.setBounds((elt[0], elt[1]))
                p.addItem(seg)


class DockDiff(Dock):
    def __init__(self, name, size, coef, frameshift, ticks, alignment=None):
        Dock.__init__(self, name=name, size=size)

        self.__plotData(coef, frameshift, ticks)
        self.__plotDiffByFrame(coef, frameshift)
        self.__applyAlignment(alignment)

        # FIXME: temporary Refinement
        self.data_plot.getAxis('left').setStyle(showValues=False)
        self.dist_plot.getAxis('left').setStyle(showValues=False)

    def __plotData(self, data, frameshift, ticks, y_scale=16e3):  # FIXME: y_scale is non sense for now!
        # Generate image data
        img = pg.ImageItem()
        img.setImage(data.T)
        img.scale(frameshift, 1.0/(data.shape[1]/y_scale))

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

    def __plotDiffByFrame(self, data, frameshift):

        data_per_frame = np.mean(data, axis=1)

        # - Generate color map
        pos, rgba_colors = zip(*_cmapToColormap(matplotlib.cm.jet, alpha=150))
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


    def __applyAlignment(self, alignment):
        for p in self.widgets:
            for i, elt in enumerate(alignment):
                boundary = pg.InfiniteLine(pos=elt[0], angle=90, pen={'color': "F009", "width": 2})
                p.addItem(boundary)

            boundary = pg.InfiniteLine(pos=alignment[-1][1], angle=90, pen={'color': "F009", "width": 2})
            p.addItem(boundary)



class DockAlignment(Dock):
    def __init__(self, name, size, alignment, wav=None):
        Dock.__init__(self, name=name, size=size)

        self.alignment = alignment
        self.wav = wav
        self.__plotAlignment(alignment)

        # FIXME: temporary refinement
        self.alignment_plot.getAxis('left').setStyle(showValues=False)

    def __plotAlignment(self, alignment):
        alignment_plot = pg.PlotWidget(name=self.name())

        for i, elt in enumerate(alignment):
            # Add boundaries
            seg = pg.LinearRegionItem(movable=False)
            seg.setBounds((elt[0], elt[1]))
            alignment_plot.addItem(seg)

            # Add label
            label = pg.TextItem(text=elt[2],anchor=(0.5,0.5))
            alignment_plot.addItem(label)
            label.setPos((elt[1]+elt[0])/2, 0.5)

        # Force the Y range to fit the text!
        alignment_plot.setYRange(0, 1.0)

        # Save everything
        self.alignment_plot = alignment_plot
        self.addWidget(alignment_plot)
