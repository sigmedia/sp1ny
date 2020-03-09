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

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui


import sounddevice as sd

class SegmentItem(pg.LinearRegionItem):
    def __init__(self, seg_infos, wav=None, T=0):
        self.T = T
        if wav is not None:
            self.T = wav[0].shape[0]/wav[1]
        if (self.T == 0):
            raise Exception("T should be different from 0 or a wav object should be given!")
        super().__init__(movable=False, values=(0, self.T))

        # Some adaptations
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 0))
        self.setBrush(brush)
        hover_brush = QtGui.QBrush(QtGui.QColor(0, 0, 255, 100))
        self.setHoverBrush(hover_brush)

        # Get segment informations
        self.start = seg_infos[0]
        self.end = seg_infos[1]
        self.label = seg_infos[2]

        # Save wav for playback!
        self.wav = wav

        # Set the bounds
        self.setBounds((seg_infos[0], seg_infos[1]))


    def mouseClickEvent(self, ev):
        super().mouseClickEvent(ev)

        # Potentially, there is nothing to play !
        if self.wav is None:
            return

        # Extract position
        start = int(self.start * self.wav[1])
        end = int(self.end * self.wav[1])

        # Play subpart
        sd.play(self.wav[0][start:end], self.wav[1])
        status = sd.wait()


    def hoverEvent(self, ev):
        if (not ev.isExit()) and ev.acceptDrags(QtCore.Qt.LeftButton):
            self.setMouseHover(True)
        else:
            self.setMouseHover(False)
