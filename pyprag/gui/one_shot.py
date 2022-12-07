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
from pyqtgraph.dockarea import DockArea
import pyqtgraph as pg

# pyprag internal packages
from pyprag.gui.utils import cmapToColormap
from pyprag.core.wav.visualisation import WavDock
from pyprag.annotations.visualisation import AnnotationDock
from pyprag.core import DataDock
from pyprag.core import plugin_entry_list

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

    def __init__(self, wav, frameshift, annotation=None, color_map=matplotlib.cm.bone):
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

        self.annotation = annotation
        if wav is not None:
            self.wav = wav
        else:
            self.wav = (np.zeros((self.coef.shape[0])), 1 / frameshift)
        self.frameshift = frameshift

        # - Generate color map
        self.logger.debug("Generate ticks for data plotting")
        pos, rgba_colors = zip(*cmapToColormap(color_map))
        cmap = pg.ColorMap(pos, rgba_colors)
        lut = cmap.getLookupTable(0.0, 1.0, 10)
        ticks = list(enumerate(lut))
        self.ticks = [(ticks[i][0] / ticks[-1][0], ticks[i][1]) for i in range(len(ticks))]
        self.__fill()

    def __fill(self):
        """Helper to fill the dock area"""
        # Generate wav part
        self.logger.debug("Plot waveform part")
        dock_wav = WavDock("Signal", (950, 20), self.wav)

        # Generate data part
        self.logger.debug("Plot coefficient part")

        controller = plugin_entry_list[0]
        controller.setWav(self.wav[0], self.wav[1], dock_wav.wav_plot)
        controller.extract()
        controller._widget.setTicks(self.ticks)
        dock_coef = DataDock(
            controller._widget,
            controller._name,
            (950, 200),  # FIXME: deal with label name
        )

        # Generate annotation part
        if self.annotation is not None:
            self.logger.debug("Plot annotation part")
            dock_align = AnnotationDock(
                "Annotations", (950, 20), self.annotation, self.wav
            )  # Size doesn't seem to affect anything

        # Link X-Axis
        self.logger.debug("Link everything")
        dock_wav.wav_plot.setLabel("bottom", "Time", units="s")
        if self.annotation is not None:
            dock_align.reference_plot.setXLink(dock_wav.wav_plot)

        # - Add docks
        self.logger.debug("Add docks to the area")
        self.addDock(dock_wav, "left")
        if self.annotation is not None:
            self.addDock(dock_align, "top", dock_wav)
            self.addDock(dock_coef, "top", dock_align)
        else:
            self.addDock(dock_coef, "top", dock_wav)
