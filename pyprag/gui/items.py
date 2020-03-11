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

class SelectablePlotItem(pg.PlotItem):
    def __init__(self, wav=None, **kwargs):
        vb = SelectableViewBox(wav)
        kwargs["viewBox"] = vb
        super().__init__(**kwargs)
        vb.setParentItem(self)

class SegmentItem(pg.LinearRegionItem):
    def __init__(self, start, end, wav=None, movable=False, related=[]):
        super().__init__()

        self._wav = wav
        self._related =related

        # Some adaptations
        brush = QtGui.QBrush(QtGui.QColor(255, 0, 0, 50))
        self.setBrush(brush)

        # Set the bounds
        self.setRegion((start, end))


    def mouseDragEvent(self, ev):
        if not self.movable or int(ev.button() & QtCore.Qt.LeftButton) == 0:
            return
        ev.accept()

        if ev.isStart():
            bdp = ev.buttonDownPos()
            self.cursorOffsets = [l.pos() - bdp for l in self.lines]
            self.startPositions = [l.pos() for l in self.lines]
            self.moving = True

        if not self.moving:
            return

        self.lines[0].blockSignals(True)  # only want to update once
        for i, l in enumerate(self.lines):
            l.setPos(self.cursorOffsets[i] + ev.pos())
        self.lines[0].blockSignals(False)
        self.prepareGeometryChange()

        if ev.isFinish():
            self.moving = False
            self.sigRegionChangeFinished.emit(self)
        else:
            self.sigRegionChanged.emit(self)

    def setRegion(self, bounds):
        # Get segment informations
        self.start = bounds[0]
        self.end = bounds[1]
        super().setRegion(bounds)

        for s in self._related:
            s.setRegion(bounds)

    def mouseClickEvent(self, ev):
        super().mouseClickEvent(ev)

        # Check which key is pressed
        modifierPressed = QtGui.QApplication.keyboardModifiers()
        modifierName = ''

        if (ev.buttons() == QtCore.Qt.LeftButton) and ev.double():
            if (modifierPressed & QtCore.Qt.ControlModifier) == QtCore.Qt.ControlModifier:
                pass
                # Potentially, there is nothing to play !
                if self._wav is None:
                    return

                # Extract position
                start = int(self.start * self._wav[1])
                end = int(self.end * self._wav[1])

                # Play subpart
                sd.play(self._wav[0][start:end], self._wav[1])
                status = sd.wait()

            elif (modifierPressed & QtCore.Qt.ShiftModifier) == QtCore.Qt.ShiftModifier:
                self.parentWidget().setXRange(0, self.parentWidget().state["limits"]["xLimits"][1])
            elif (not modifierPressed):
                self.parentWidget().setXRange(self.start, self.end)

class AnnotationItem(SegmentItem):
    def __init__(self, seg_infos, wav=None, T=0, showLabel=True):
        self.T = T
        if wav is not None:
            self.T = wav[0].shape[0]/wav[1]

        if (self.T == 0):
            raise Exception("T should be different from 0 or a wav object should be given!")

        super().__init__(seg_infos[0], seg_infos[1], movable=False) # FIXME what to do with this, values=(0, self.T))

        self.label = seg_infos[2]

        # Some adaptations
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 0))
        self.setBrush(brush)
        hover_brush = QtGui.QBrush(QtGui.QColor(0, 0, 255, 100))
        self.setHoverBrush(hover_brush)

        # Save wav for playback!
        self.wav = wav

        # Add label
        if showLabel:
            text = pg.TextItem(text=self.label,anchor=(0.5,0.5))
            text.setPos((self.end+self.start)/2, 0.5)
            text.setParentItem(self)

    def hoverEvent(self, ev):
        if (not ev.isExit()) and ev.acceptDrags(QtCore.Qt.LeftButton):
            self.setMouseHover(True)
        else:
            self.setMouseHover(False)



class SelectableViewBox(pg.ViewBox):
    def __init__(self, wav=None, *args, **kwds):
        super().__init__(*args, **kwds)
        self.dragPoint = None
        self._select = False
        self._wav = wav

    def mouseDragEvent(self, ev):
        # Check which key is pressed
        modifierPressed = QtGui.QApplication.keyboardModifiers()
        modifierName = ''

        # Ignore any event while selecting the region
        if not self._select:
            if (ev.buttons() != QtCore.Qt.LeftButton) or \
               ((modifierPressed & QtCore.Qt.ShiftModifier) != QtCore.Qt.ShiftModifier):
                super().mouseDragEvent(ev)
                return

        # Start to define the region
        if ev.isStart():
            # Compute start position
            start_pos = ev.buttonDownPos()
            start = self.mapSceneToView(start_pos).x()

            # Compute end position
            end_pos = ev.pos()
            end = self.mapSceneToView(end_pos).x()

            #
            # Check
            if self.dragPoint is not None:
                self.dragPoint.setRegion((start, end))
            else:
                self.dragPoint = SegmentItem(start, end, wav=self._wav)
                self.parentWidget().addItem(self.dragPoint)

            self._select = True

        # Finish
        elif ev.isFinish():
            self._select = False

        # Definition of the region in progress
        else:
            if self.dragPoint is not None:
                # Compute start position
                start_pos = ev.buttonDownPos()
                start = self.mapSceneToView(start_pos).x()

                # Compute end position
                end_pos = ev.pos()
                end = self.mapSceneToView(end_pos).x()

                # Update region
                self.dragPoint.setRegion((start, end))
            else:
                ev.ignore()
                return

        # Indicate that the event has been accepted and everything has been done
        ev.accept()
