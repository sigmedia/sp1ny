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
class SegmentItem(pg.LinearRegionItem):
    def __init__(self, seg_infos, global_end):
        super().__init__(movable=False, values=(0, global_end))

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
