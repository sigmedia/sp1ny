#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module providing the class OneShotArea

LICENSE
"""
# Logging
import logging

# Linear algebra
import numpy as np

# Plotting
import matplotlib.cm
from pyqtgraph.dockarea import *
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

# pyprag internal packages
from pyprag.gui.utils import *
from pyprag.gui.docks import *

#####################################################################################################
# Classes
#####################################################################################################

class OneShotArea(DockArea):
    """DockArea filled with a plot containing a waveform and a give data (matrix only for now) as well
    as optional annotations.

    Attributes
    ----------
    wav : tuple(np.array, int)
        The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

    coef : np.array
       The matrix of coefficients to render

    annotation: pypgrag.annotation.AnnotationLoader
       The annotations if available, else None

    ticks : TODO
        The color map ticks
    """
    def __init__(self, wav, coef, frameshift, annotation=None, color_map=matplotlib.cm.bone):
        """
        Parameters
        ----------
        wav : tuple(np.array, int)
            The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

        coef : np.array
           The matrix of coefficients to render

        frameshift : float
           The frameshift used to extract the coefficients from the waveform

        annotation: pypgrag.annotation.AnnotationLoader, optional
           The annotation of object. (Default: None)

        color_map: matplotlib.cm.ColorMap, optional
           The color map used for the data rendering. (default: matplotlib.cm.bone)
        """
        # Superclass initialisation
        DockArea.__init__(self)

        self.logger = logging.getLogger("OneShotArea")

        self.wav = wav
        self.coef = coef
        self.frameshift = frameshift
        self.annotation = annotation

        # - Generate color map
        self.logger.debug("Generate ticks for data plotting")
        pos, rgba_colors = zip(*cmapToColormap(color_map))
        cmap =  pg.ColorMap(pos, rgba_colors)
        lut = cmap.getLookupTable(0.0, 1.0, 10)
        ticks = list(enumerate(lut))
        self.ticks = [(ticks[i][0]/ticks[-1][0], ticks[i][1]) for i in range(len(ticks))]

        self.__fill()

    def __fill(self):
        """Helper to fill the dock area

        """
        # Generate reference part
        self.logger.debug("Plot coefficient part")
        dock_coef = DockWithWav("Signal", (950, 200), # FIXME: deal with label name
                                self.coef, self.wav,
                                self.frameshift, self.ticks)

        # Generate annotation part
        if self.annotation is not None:
            self.logger.debug("Plot annotation part")
            dock_align = DockAnnotation("Annotations", (950, 20),
                                       self.annotation, self.wav) # Size doesn't seem to affect anything
            reference_plot = dock_align.reference_plot
        else:
            reference_plot = dock_coef.wav_plot


        # Fix x-axis
        self.logger.debug("Link everything")
        dock_coef.data_plot.setXLink(reference_plot)
        if self.annotation is not None:
            dock_coef.wav_plot.setXLink(reference_plot)

        # Set axes labels
        reference_plot.setLabel('bottom', 'Time', units='s')

        # - Add docks
        self.logger.debug("Add docks to the area")
        if self.annotation is not None:
            self.addDock(dock_align, "left")
            self.addDock(dock_coef, "top", dock_align)
        else:
            self.addDock(dock_coef, "left")
