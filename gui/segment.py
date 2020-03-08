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

class SegmentItem(pg.LinearRegionItem):
    def __init__(self, seg_infos, global_end):
        super().__init__(movable=False, values=(0, global_end))

        # Some adaptations
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 0))
        self.setBrush(brush)
        hover_brush = QtGui.QBrush(QtGui.QColor(0, 0, 255, 100))
        self.setHoverBrush(hover_brush)

        # Get segment informations
        self.start = seg_infos[0]
        self.end = seg_infos[1]
        self.label = seg_infos[2]

        # Set the bounds
        self.setBounds((seg_infos[0], seg_infos[1]))


    def mouseClickEvent(self, ev):
        super().mouseClickEvent(ev)

        # For now just print the label
        print(self.label)


    def hoverEvent(self, ev):
        if (not ev.isExit()) and ev.acceptDrags(QtCore.Qt.LeftButton):
            self.setMouseHover(True)
        else:
            self.setMouseHover(False)
