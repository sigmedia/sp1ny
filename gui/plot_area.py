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

# Utils
import collections

#####################################################################################################
# Helper
#####################################################################################################
def _cmapToColormap(cmap, nTicks=16, alpha=255):
    """
    Converts a Matplotlib cmap to pyqtgraphs colormaps. No dependency on matplotlib.
    Parameters:
    *cmap*: Cmap object. Imported from matplotlib.cm.*
    *nTicks*: Number of ticks to create when dict of functions is used. Otherwise unused.
    """

    # Case #1: a dictionary with 'red'/'green'/'blue' values as list of ranges (e.g. 'jet')
    # The parameter 'cmap' is a 'matplotlib.colors.LinearSegmentedColormap' instance ...
    if hasattr(cmap, '_segmentdata'):
        colordata = getattr(cmap, '_segmentdata')
        if ('red' in colordata) and isinstance(colordata['red'], collections.Sequence):

            # collect the color ranges from all channels into one dict to get unique indices
            posDict = {}
            for idx, channel in enumerate(('red', 'green', 'blue')):
                for colorRange in colordata[channel]:
                    posDict.setdefault(colorRange[0], [-1, -1, -1])[idx] = colorRange[2]

            indexList = list(posDict.keys())
            indexList.sort()
            # interpolate missing values (== -1)
            for channel in range(3):  # R,G,B
                startIdx = indexList[0]
                emptyIdx = []
                for curIdx in indexList:
                    if posDict[curIdx][channel] == -1:
                        emptyIdx.append(curIdx)
                    elif curIdx != indexList[0]:
                        for eIdx in emptyIdx:
                            rPos = (eIdx - startIdx) / (curIdx - startIdx)
                            vStart = posDict[startIdx][channel]
                            vRange = (posDict[curIdx][channel] - posDict[startIdx][channel])
                            posDict[eIdx][channel] = rPos * vRange + vStart
                        startIdx = curIdx
                        del emptyIdx[:]
            for channel in range(3):  # R,G,B
                for curIdx in indexList:
                    posDict[curIdx][channel] *= 255

            rgb_list = [[i, posDict[i]] for i in indexList]

        # Case #2: a dictionary with 'red'/'green'/'blue' values as functions (e.g. 'gnuplot')
        elif ('red' in colordata) and isinstance(colordata['red'], collections.Callable):
            indices = np.linspace(0., 1., nTicks)
            luts = [np.clip(np.array(colordata[rgb](indices), dtype=np.float), 0, 1) * 255 \
                    for rgb in ('red', 'green', 'blue')]
            rgb_list = zip(indices, list(zip(*luts)))

    # If the parameter 'cmap' is a 'matplotlib.colors.ListedColormap' instance, with the attributes 'colors' and 'N'
    elif hasattr(cmap, 'colors') and hasattr(cmap, 'N'):
        colordata = getattr(cmap, 'colors')
        # Case #3: a list with RGB values (e.g. 'seismic')
        if len(colordata[0]) == 3:
            indices = np.linspace(0., 1., len(colordata))
            scaledRgbTuples = [(rgbTuple[0] * 255, rgbTuple[1] * 255, rgbTuple[2] * 255) for rgbTuple in colordata]
            rgb_list = zip(indices, scaledRgbTuples)

        # Case #4: a list of tuples with positions and RGB-values (e.g. 'terrain')
        # -> this section is probably not needed anymore!?
        elif len(colordata[0]) == 2:
            rgb_list = [(idx, (vals[0] * 255, vals[1] * 255, vals[2] * 255)) for idx, vals in colordata]

    # Case #X: unknown format or datatype was the wrong object type
    else:
        raise ValueError("[cmapToColormap] Unknown cmap format or not a cmap!")

    # Convert the RGB float values to RGBA integer values
    return list([(pos, (int(r), int(g), int(b), alpha)) for pos, (r, g, b) in rgb_list])



#####################################################################################################
# Classes
#####################################################################################################

class PlotArea(DockArea):
    def __init__(self, ref_infos, other_infos, dist, frameshift, alignment=None, color_map=matplotlib.cm.bone):
        # Superclass initialisation
        DockArea.__init__(self)

        # - Set useful variables
        self.ref = ref_infos[0]
        self.ref_wav = ref_infos[1]
        self.ref_filename = ref_infos[2]

        self.other = other_infos[0]
        self.other_wav = other_infos[1]
        self.other_filename = other_infos[2]

        self.dist = dist
        self.frameshift = frameshift
        self.y_scale = 16e3
        self.alignment = alignment

        # - Generate color map
        pos, rgba_colors = zip(*_cmapToColormap(color_map))
        cmap =  pg.ColorMap(pos, rgba_colors)
        lut = cmap.getLookupTable(0.0, 1.0, 10)
        ticks = list(enumerate(lut))
        self.ticks = [(ticks[i][0]/ticks[-1][0], ticks[i][1]) for i in range(len(ticks))]

        self.__fill()

    def __fill(self):

        if self.alignment is None:
            self.alignment = []

        # Generate reference part
        dock_ref = DockWithWav("Reference", (950, 200),
                               self.ref, self.ref_wav,
                               self.frameshift, self.ticks,
                               self.alignment)
        dock_ref.setToolTip(self.ref_filename)

        # Generate other part
        dock_other = DockWithWav("Other", (950, 200),
                                 self.other, self.other_wav,
                                 self.frameshift, self.ticks,
                                 self.alignment)
        dock_other.setToolTip(self.other_filename)

        # Generate difference map part
        dock_diff = DockDiff("Difference", (950, 200),
                             self.dist,
                             self.frameshift, self.ticks,
                             self.alignment)

        # Generate alignment part
        dock_align = DockAlignment("Lab", (950, 20), self.alignment) # Size doesn't seem to affect anything

        # Fix x-axis
        dock_ref.data_plot.setXLink(dock_align.alignment_plot)
        dock_ref.wav_plot.setXLink(dock_align.alignment_plot)
        dock_other.data_plot.setXLink(dock_align.alignment_plot)
        dock_other.wav_plot.setXLink(dock_align.alignment_plot)
        dock_diff.data_plot.setXLink(dock_align.alignment_plot)
        dock_diff.dist_plot.setXLink(dock_align.alignment_plot)

        # Set axes labels
        dock_align.widgets[0].setLabel('bottom', 'Time', units='s')

        # - Add docks
        self.addDock(dock_align, "left")
        self.addDock(dock_ref, "top", dock_align)
        self.addDock(dock_other, "top", dock_ref)
        self.addDock(dock_diff, "top", dock_other)



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
        wav_plot.setMaximumHeight(50) # FIXME: hardcoded height

        # Add the wav plot to the dock!
        self.wav_plot = wav_plot
        self.addWidget(wav_plot)

    def __applyAlignment(self, alignment):
        for p in self.widgets:
            for i, elt in enumerate(alignment):
                boundary = pg.InfiniteLine(pos=elt[0], angle=90, pen={'color': "F009", "width": 2})
                p.addItem(boundary)

            boundary = pg.InfiniteLine(pos=alignment[-1][1], angle=90, pen={'color': "F009", "width": 2})
            p.addItem(boundary)


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
    def __init__(self, name, size, alignment):
        Dock.__init__(self, name=name, size=size)

        self.__plotAlignment(alignment)

        # FIXME: temporary refinement
        self.alignment_plot.getAxis('left').setStyle(showValues=False)

    def __plotAlignment(self, alignment):
        alignment_plot = pg.PlotWidget(name=self.name())

        for i, elt in enumerate(alignment):
            # Add boundaries
            boundary = pg.InfiniteLine(pos=elt[0], angle=90, pen={'color': "F00", "width": 2})
            alignment_plot.addItem(boundary)

            # Add label
            label = pg.TextItem(text=elt[2],anchor=(0.5,0.5))
            alignment_plot.addItem(label)
            label.setPos((elt[1]+elt[0])/2, 0.5)

        # Add final missing boundary
        boundary = pg.InfiniteLine(pos=alignment[-1][1], angle=90, pen={'color': "F00", "width": 2})
        alignment_plot.addItem(boundary)

        # Force the Y range to fit the text!
        alignment_plot.setYRange(0, 1.0)

        # Save everything
        self.alignment_plot = alignment_plot
        self.addWidget(alignment_plot)
