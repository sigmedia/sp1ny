#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module to provide the different areas which are comparing *aligned* signals

LICENSE
"""

# Linear algebra
import numpy as np
import scipy as sp
from scipy import signal

# Plotting
import matplotlib.cm
from pyqtgraph.dockarea import *
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

# Utils
import collections

# pyprag internal imports
from pyprag.gui.utils import *
from pyprag.gui.docks import *

#####################################################################################################
# Classes
#####################################################################################################

class NSIMComparisonArea(DockArea):
    """Dock area containing (from top to bottom):
        - A dock containg a NSIM map and the corresponding average per frame
        - A dock containing a wav plot and the corresponding data for the other signal
        - A dock containing a wav plot and the corresponding data for the reference signal
        - A dock containing the annotation plots (if any available)

    Attributes
    ----------
    ref : np.array
        The reference coefficients (matrix)

    ref_wav : tuple(np.array, int)
        The reference signal information of the reference as loaded using librosa. The tuple contain an array of samples and the sample rate.

    ref_filename : str
        The filename of the reference coefficients

    other : np.array
        The other signal coefficients (matrix)

    other_wav : tuple(np.array, int)
        The other signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

    other_filename : str
        The filename of the other signal coefficients

    frameshift : float
        The frameshift used to extract the coefficients ftrom the signals

    nsim : float
        The NSIM value

    nmap : np.array
        The intermediate matrix averaged to get the final NSIM

    y_scale : TODO
        NOT TO BE USED FOR NOW

    annotation : pyprag.annotation.AnnotationLoader
        The annotations if available, else None


    ticks : TODO
        The color map ticks

    """
    def __init__(self, ref_infos, other_infos, frameshift, annotation=None, color_map=matplotlib.cm.bone):
        # Superclass initialisation
        DockArea.__init__(self)

        # - Set useful variables
        self.ref = ref_infos[0]
        self.ref_wav = ref_infos[1]
        self.ref_filename = ref_infos[2]

        self.other = other_infos[0]
        self.other_wav = other_infos[1]
        self.other_filename = other_infos[2]

        self.frameshift = frameshift
        self.y_scale = 16e3
        self.annotation = annotation

        # Compute NSIM
        nsim_cptr = NSIM(self.ref, self.other)
        [self.nsim, self.nmap] = nsim_cptr.compute()


        # # Compute proportion
        # prop = np.count_nonzero(nmap >= 0.99) * 100.0 / (nmap.shape[0] * nmap.shape[1])
        # print("prop = %03.2f %%" % prop)

        # # Filter out values
        # nmap_ma = np.ma.masked_where(nmap>=0.99, nmap)
        # print(np.mean(nmap_ma))

        # - Generate color map
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
        dock_ref = DockWithWav("Reference", (950, 200),
                               self.ref, self.ref_wav,
                               self.frameshift, self.ticks)
        dock_ref.setToolTip(self.ref_filename)

        # Generate other part
        dock_other = DockWithWav("Other", (950, 200),
                                 self.other, self.other_wav,
                                 self.frameshift, self.ticks)
        dock_other.setToolTip(self.other_filename)

        # Generate difference map part
        dock_diff = DockAvg("Difference", (950, 200),
                             self.nmap,
                             self.frameshift, self.ticks)

        # Generate annotation part
        if self.annotation is not None:
            dock_align = DockAnnotation("Lab", (950, 20),
                                       self.annotation, self.ref_wav) # Size doesn't seem to affect anything
            reference_plot = dock_align.reference_plot
        else:
            reference_plot = dock_ref.wav_plot

        # Fix x-axis
        dock_ref.data_plot.setXLink(reference_plot)
        dock_ref.wav_plot.setXLink(reference_plot)
        dock_other.data_plot.setXLink(reference_plot)
        dock_other.wav_plot.setXLink(reference_plot)
        dock_diff.avg_plot.setXLink(reference_plot)
        dock_diff.avg_plot.setXLink(reference_plot)

        # Set axes labels
        reference_plot.setLabel('bottom', 'Time', units='s')

        # - Add docks
        if self.annotation is not None:
            self.addDock(dock_align, "left")
            self.addDock(dock_ref, "top", dock_align)
        else:
            self.addDock(dock_ref, "left")

        self.addDock(dock_other, "top", dock_ref)
        self.addDock(dock_diff, "top", dock_other)


class NSIM:
    """Helper to compute the Neurogram Similarity Index Measure (NSIM) and its corresponding map

    Attributes
    ----------
    _window : np.array
        The gaussian window matrix

    _r : np.array
        The reference data matrix

    _d : np.array
        The "degraded" data matrix

    """

    def __init__(self, r, d):
        """
        Parameters
        ----------
        self : type
            description

        r : np.array
            The reference data matrix

        d : np.array
            The "degraded" data matrix

        """
        self._window =  np.array([[0.0113, 0.0838, 0.0113],
                                  [0.0838, 0.6193, 0.0838],
                                  [0.0113, 0.0838, 0.0113]])
        self._window = self._window / np.sum(self._window)
        self._r = r
        self._d = d

    def compute(self):
        """NSIM Metric based on visqol implementation

        Returns
        -------
        tuple(float, np.array)
           a tuple containing the NSIM value and the intermediate matrix

        """
        # 2-D Gaussian filter of size 3 with std=0.5
        window_rotated = np.rot90(self._window, 2)

        # Prepare smoothing coefficient
        L = 160 # FIXME: hardcoded
        C1 = np.power(0.01 * L, 2)
        C2 = np.power(0.03 * L, 2) / 2

        # Mean part
        m_r = signal.convolve2d(self._r, window_rotated, 'valid') # Filter2 in matlab
        m_d = signal.convolve2d(self._d, window_rotated, 'valid') # Filter2 in matlab
        m_r_sq = m_r * m_r
        m_d_sq = m_d * m_d
        m_r_m_d = m_r * m_d

        # Std part
        s_r_sq = signal.convolve2d(self._r*self._r, window_rotated, 'valid') - m_r_sq # Filter2 in matlab
        s_d_sq = signal.convolve2d(self._d*self._d, window_rotated, 'valid') - m_d_sq # Filter2 in matlab
        s_r_d = signal.convolve2d(self._r*self._d, window_rotated, 'valid') - m_r_m_d # Filter2 in matlab
        s_r = np.sign(s_r_sq) * np.sqrt(np.abs(s_r_sq))
        s_d = np.sign(s_d_sq) * np.sqrt(np.abs(s_d_sq))

        # Compute subparts
        L_r_d = (2 * m_r * m_d + C1) / (m_r_sq + m_d_sq + C1) # Luminance
        S_r_d = (s_r_d + C2) / (s_r * s_d + C2) # Structural

        # Compute nsim
        nmap = L_r_d * S_r_d
        nsim = np.mean(nmap)

        return (nsim, nmap)
