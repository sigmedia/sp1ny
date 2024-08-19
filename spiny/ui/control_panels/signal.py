#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION


LICENSE
    This script is in the public domain, free from copyrights or restrictions.
    Created: 24 October 2019
"""

# Plotting & rendering
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets


class EqWidget(QtWidgets.QGroupBox):
    def __init__(self, parent, wav):
        super().__init__(title="Equalizer", parent=parent)

        self._signal = wav[0]
        self._sampling_rate = wav[1]

        self.__define_sliders__()

    def __define_sliders__(self):

        self._frequencies = [50, 200, 1000, 2000, 4000, 8000, 16000]
        self._slider_array = []

        layout = QtWidgets.QHBoxLayout()

        prev_freq = 0
        for freq in self._frequencies:

            cur_slider = EqSlider(prev_freq, freq, self)
            layout.addWidget(cur_slider)
            prev_freq = freq

        self.setLayout(layout)


class EqSlider(QtWidgets.QWidget):
    def __init__(self, lower_freq, upper_freq, parent=None):
        super().__init__(parent=parent)
        self._verticalLayout = QtWidgets.QVBoxLayout(self)
        self._label = QtGui.QLabel(self)
        self._verticalLayout.addWidget(self._label)
        self._horizontalLayout = QtWidgets.QHBoxLayout()
        spacerItem = QtWidgets.QSpacerItem(0, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self._horizontalLayout.addItem(spacerItem)
        self._slider = QtGui.QSlider(self)
        self._slider.setOrientation(QtCore.Qt.Vertical)
        self._horizontalLayout.addWidget(self._slider)
        spacerItem1 = QtWidgets.QSpacerItem(0, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self._horizontalLayout.addItem(spacerItem1)
        self._verticalLayout.addLayout(self._horizontalLayout)
        self.resize(self.sizeHint())

        self._slider.setMinimum(-120)
        self._slider.setMaximum(0)
        self._slider.setValue(0)
        self._slider.setTickPosition(QtGui.QSlider.TicksBelow)
        self._slider.setTickInterval(10)  # FIXME: hardcoded

        self._lower_freq = lower_freq
        self._upper_freq = upper_freq

        self.setLabelValue(upper_freq)

    def setLabelValue(self, upper_freq):
        if upper_freq >= 1000:
            self._label.setText(f"< {int(upper_freq/1000):2d}k")
        else:
            self._label.setText(f"< {upper_freq}")
