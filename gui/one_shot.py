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
# Logging
import logging

# Linear algebra
import numpy as np

# Plotting
import matplotlib.cm
from pyqtgraph.dockarea import *
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

#
from .utils import *
from .docks import *

#####################################################################################################
# Classes
#####################################################################################################

class OneShotArea(DockArea):
    def __init__(self, wav, coef, frameshift, alignment=None, color_map=matplotlib.cm.bone):
        # Superclass initialisation
        DockArea.__init__(self)

        self.logger = logging.getLogger("OneShotArea")

        self.wav =wav
        self.coef = coef
        self.frameshift = frameshift
        self.y_scale = 16e3
        self.alignment = alignment

        # - Generate color map
        self.logger.debug("Generate ticks for data plotting")
        pos, rgba_colors = zip(*cmapToColormap(color_map))
        cmap =  pg.ColorMap(pos, rgba_colors)
        lut = cmap.getLookupTable(0.0, 1.0, 10)
        ticks = list(enumerate(lut))
        self.ticks = [(ticks[i][0]/ticks[-1][0], ticks[i][1]) for i in range(len(ticks))]


        self.__fill()

    def __fill(self):
        # Generate reference part
        self.logger.debug("Plot coefficient part")
        dock_coef = DockWithWav("??", (950, 200), # FIXME: deal with label name
                                self.coef, self.wav,
                                self.frameshift, self.ticks,
                                self.alignment)

        # Generate alignment part
        self.logger.debug("Plot alignment part")
        dock_align = DockAlignment("Lab", (950, 20),
                                   self.alignment, self.wav) # Size doesn't seem to affect anything

        # Fix x-axis
        self.logger.debug("Link everything")
        dock_coef.data_plot.setXLink(dock_align.alignment_plot)
        dock_coef.wav_plot.setXLink(dock_align.alignment_plot)

        # Set axes labels
        dock_align.alignment_plot.setLabel('bottom', 'Time', units='s')

        # - Add docks
        self.logger.debug("Add docks to the area")
        self.addDock(dock_align, "left")
        self.addDock(dock_coef, "top", dock_align)
