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
import scipy as sp
from scipy import signal

# Plotting
import matplotlib.cm
from pyqtgraph.dockarea import *
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

# Utils
import collections

#
from .utils import *
from .docks import *

#####################################################################################################
# Classes
#####################################################################################################

class NSIMComparisonArea(DockArea):
    def __init__(self, ref_infos, other_infos, frameshift, alignment=None, color_map=matplotlib.cm.bone):
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
        self.alignment = alignment

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

        if self.alignment is None:
            segments = []
        else:
            segments = self.alignment.segments

        # Generate reference part
        dock_ref = DockWithWav("Reference", (950, 200),
                               self.ref, self.ref_wav,
                               self.frameshift, self.ticks,
                               segments)
        dock_ref.setToolTip(self.ref_filename)

        # Generate other part
        dock_other = DockWithWav("Other", (950, 200),
                                 self.other, self.other_wav,
                                 self.frameshift, self.ticks,
                                 segments)
        dock_other.setToolTip(self.other_filename)

        # Generate difference map part
        dock_diff = DockDiff("Difference", (950, 200),
                             self.nmap,
                             self.frameshift, self.ticks,
                             segments)

        # Generate alignment part
        dock_align = DockAlignment("Lab", (950, 20),
                                   segments, self.ref_wav) # Size doesn't seem to affect anything

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


class NSIM:
    def __init__(self, r, d):
        self._window =  np.array([[0.0113, 0.0838, 0.0113],
                                  [0.0838, 0.6193, 0.0838],
                                  [0.0113, 0.0838, 0.0113]])
        self._window = self._window / np.sum(self._window)
        self._r = r
        self._d = d

    def compute(self):
        """NSIM Metric based on visqol implementation

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
