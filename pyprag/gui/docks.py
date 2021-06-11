#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module containing classes defining new docks to be used to render the data and the waveform
LICENSE
"""

# Linear algebra
import numpy as np

# Plotting
import matplotlib.cm
from pyqtgraph.dockarea import Dock
from pyqtgraph.Qt import QtGui
import pyqtgraph as pg

# Pyprag imports
from pyprag.gui.utils import *
from pyprag.gui.items import *
from pyprag.gui.widgets import *

###############################################################################
# Classes
###############################################################################
class DockData(Dock):
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
    def __init__(self, name, size, data, frameshift, ticks, wav):
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

        self.data = data
        self.wav = wav
        max_dur = self.data.shape[0] * frameshift

        self.__plotData(frameshift, ticks)

        # Label space
        self.data_plot.getAxis('left').setWidth(50)

    def __plotData(self, frameshift, ticks):
        """Helper to plot the data

        Parameters
        ----------
        frameshift : float
            The frameshift used to extract the signals

        ticks : TODO
            The color map ticks

        y_scale : int
            SHOULD NOT BE USED FOR NOW!

        """
        lim_factor = 1.1
        self.data_plot = SelectableImagePlotWidget(self.data, frameshift, ticks, self.wav[1] / 2.0,
                                                   name="%s coef" % self.name,
                                                   wav=self.wav)
        self.data_plot.setLimits(xMax=self.data.shape[0]*frameshift*lim_factor)
        self.data_plot.hideAxis('bottom')

        # Add plot
        # self.data_plot.disableAutoRange()
        self.addWidget(self.data_plot)


class DockWav(Dock):
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
        self.wav_plot.getAxis('left').setWidth(50)

        # # Reactivate autorange
        # self.wav_plot.autoRange()


    def __plotWav(self):
        """Helper to plot the waveform

        Parameters
        ----------
        max_dur : float
            The maximum duration in seconds. It is mainly used in the case that the annotations require more space than the waveform

        """

        self.wav_plot = SelectableWavPlotWidget(self.wav, name="%s waveform" % self.name)
        self.addWidget(self.wav_plot)


class DockAvg(Dock):
    """Dock containing a data surface plot (matrix data for now) and the standard 2-D curve plot

    The surface plot corresponds to the rendering of the data matrix and the curve plot to the
    average of each columns of the data matrix.

    Attributes
    ----------
    data : np.array
        matrix containing the data to render

    wav : tuple(np.array, int)
        The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

    data_plot :
        The plot item rendering the data part

    avg_plot :
        The plot item rendering the waveform

    """
    def __init__(self, name, size, data, frameshift, ticks, y_scale):
        Dock.__init__(self, name=name, size=size)

        self.data = data
        self._y_scale = y_scale
        self.__plotData(frameshift, ticks)
        self.__plotDiffByFrame(frameshift)

        # FIXME: temporary Refinement
        self.data_plot.getAxis('left').setLabel("Difference map")
        self.data_plot.getAxis('left').setWidth(50)
        self.avg_plot.getAxis('left').setLabel("Difference by frame")
        self.avg_plot.getAxis('left').setWidth(50)

    def __plotData(self, frameshift, ticks):  # FIXME: y_scale is non sense for now!
        """Helper to plot the data

        Parameters
        ----------
        frameshift : float
            The frameshift used to extract the signals

        ticks : TODO
            The color map ticks

        y_scale : int
            SHOULD NOT BE USED FOR NOW!

        """
        # Generate image data
        img = pg.ImageItem()
        img.setImage(self.data.T)
        img.setTransform(QtGui.QTransform.fromScale(frameshift, 1.0/(self.data.shape[1]/self._y_scale)))

        # Define and assign histogram
        hist = pg.HistogramLUTWidget()
        hist.setImageItem(img)
        hist.gradient.restoreState(
            {'mode': 'rgb', 'ticks': ticks}
        )

        # Generate plot
        self.data_plot = pg.PlotWidget(name="%s coef" % self.name)
        self.data_plot.addItem(img)
        self.data_plot.hideAxis('bottom')

        # Add plot
        self.addWidget(self.data_plot)

    def __plotDiffByFrame(self, frameshift):
        """Helper to the average data value per frame

        Parameters
        ----------
        frameshift : float
            The frameshift used to extract the signals

        """
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
        self.avg_plot = pg.PlotWidget(name="Distance per frame")
        pc = pg.PlotCurveItem(x=np.linspace(0, data_per_frame.shape[0]*frameshift, data_per_frame.shape[0]),
                              y=data_per_frame,  brush=brush, fillLevel=0, pen=None)
        self.avg_plot.addItem(pc)
        # avg_plot.plot(x=np.linspace(0, data_per_frame.shape[0]*x_scale, data_per_frame.shape[0]),
        #                y=data_per_frame, brush=brush)
        self.avg_plot.setMaximumHeight(70)

        # Add plot to dock!
        self.addWidget(self.avg_plot)


class DockAnnotation(Dock):
    """Dock containing annotation informations

    Attributes
    ----------
    annotation: pyprag.annotation.AnnotationLoader
        The annotation loader object

    wav : tuple(np.array, int)
        The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

    reference_plot : pg.PlotWidget
        The reference annotation tier rendering as we have a plot per tier

    """
    def __init__(self, name, size, annotation, wav):
        """
        Parameters
        ----------
        size : type
            description

        annotation: pyprag.annotation.AnnotationLoader
            The annotation loader object

        wav : tuple(np.array, int)
            The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate

        """
        Dock.__init__(self, name=name, size=size)

        # Define some attributes
        self.annotation = annotation
        self.wav = wav

        # Render everything
        self.__plotAnnotation()

        # FIXME: temporary refinement
        for w in self.widgets:
            w.getAxis('left').setWidth(50)
            w.getAxis('left').setStyle(showValues=False)
            w.autoRange()

    def __plotAnnotation(self):
        """Helper to render the annotations
        """
        lim_factor = 1.1
        T_max = self.wav[0].shape[0]/self.wav[1]
        for k in self.annotation.segments:
            annotation_plot = pg.PlotWidget(name="%s_%s" % (self.name(), k))
            annotation_plot.disableAutoRange()
            annotation_plot.getAxis("left").setLabel(k)
            annotation_plot.setYRange(0, 1)
            for i, elt in enumerate(self.annotation.segments[k]):
                # Generate region item
                seg = AnnotationItem(elt, self.wav)
                annotation_plot.addItem(seg)


            if T_max < self.annotation.segments[k][-1][1]:
                T_max = self.annotation.segments[k][-1][1]

            self.addWidget(annotation_plot)

        # Define a reference plot and lock everything for thing to it
        self.reference_plot = self.widgets[-1]
        self.reference_plot.setLimits(xMax=T_max*lim_factor)
        self.reference_plot.hideAxis('bottom')
        for i in range(len(self.widgets)-1):
            self.widgets[i].hideAxis('bottom')
            self.widgets[i].setXLink(self.reference_plot)
            self.widgets[i].setLimits(xMax=T_max*lim_factor)



class ComparisonDock(Dock):
    """Dock containinhg a data surface plot (matrix data for now) and the corresponding waveform

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
    def __init__(self, name, size, data_ref, data_other, ticks, y_scale):
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

        self._data_ref = data_ref
        self._data_other = data_other
        self._y_scale = y_scale
        self.__plotData(ticks)

    def __plotData(self, ticks):  # FIXME: y_scale is non sense for now!
        """Helper to plot the data

        Parameters
        ----------
        frameshift : float
            The frameshift used to extract the signals

        ticks : TODO
            The color map ticks

        y_scale : int
            SHOULD NOT BE USED FOR NOW!

        """
        self.data_plot = pg.PlotWidget()

        # Generate image data
        img = pg.ImageItem()
        img.setImage(self._data_ref.T)

        # Define and assign histogram
        self.hist = pg.HistogramLUTWidget()
        self.hist.setImageItem(img)
        self.hist.gradient.restoreState(
            {'mode': 'rgb', 'ticks': ticks}
        )

        # Generate plot
        self.data_plot.plotItem = SelectablePlotItem()
        self.data_plot.plotItem.getViewBox().addItem(img)
        self.data_plot.setCentralItem(self.data_plot.plotItem)

        # Add plot
        self.data_plot.disableAutoRange()
        self.addWidget(self.data_plot)
