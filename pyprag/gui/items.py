#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module providing some specific items for annotation and highlight purpose.

LICENSE
"""

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui

from pyprag.components.wav.player import player

###############################################################################
# Classes
###############################################################################

class SelectablePlotItem(pg.PlotItem):
    """PlotItem using a SelectableViewBox instead of a standard pg.ViewBox

    """
    def __init__(self, wav=None, **kwargs):
        """
        Parameters
        ----------

        wav : tuple(np.array, int), optional
            The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate. (default: None)

        kwargs : keyword arguments
            Used to transmit values to pg.plotItem. *The keyword viewBox is ignored*

        """
        vb = SelectableViewBox(wav)
        kwargs["viewBox"] = vb
        super().__init__(**kwargs)
        vb.setParentItem(self)


class SegmentItem(pg.LinearRegionItem):
    """A segment item which is a specific pg.LinearRegionItem

    Attributes
    ----------
    start : float
        The start position (in seconds)

    end : float
        The end position (in seconds)

    wav : tuple(np.array, int)
        The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

    movable : bool
        Indicate if the segment can be moved (start and end are changing)

    related : list
        List of related segments (instances of SegmentItem)

    """

    def __init__(self, start, end, wav=None, movable=False, related=[]):
        """
        Parameters
        ----------
        start : float
            The start position (in seconds)

        end : float
            The end position (in seconds)

        wav : tuple(np.array, int), optional
            The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate. (default: None)

        movable : bool
            Indicate if the segment can be moved (start and end are changing). (default: False)

        related : list
            List of related segments (instances of SegmentItem). (default: [])
        """
        super().__init__()

        self._wav = wav
        self._related =related

        # Some adaptations
        brush = QtGui.QBrush(QtGui.QColor(255, 0, 0, 50))
        self.setBrush(brush)

        # Set the bounds
        self.setRegion((start, end))

    def setRegion(self, bounds):
        """Set the values for the edges of the region. If related items have been specified, they are
        updated with the same bound values.

        Parameters
        ----------
        bounds : (float, float)
            the new (start, end) values

        """
        # Get segment informations
        self.start = bounds[0]
        self.end = bounds[1]
        assert self.end >= self.start
        super().setRegion(bounds)

        for s in self._related:
            s.setRegion(bounds)


    def mouseDragEvent(self, ev):
        """The item dragging event handler.

        Parameters
        ----------
        ev : pg.MouseDragEvent

        """
        super().mouseDragEvent(ev)

    def mouseClickEvent(self, ev):
        """The click event handler.

        Additionnal operations are available:
           - C-<double click> = play if wav is not None
           - S-<double click> = unzoom
           - <double click> = zoom

        Parameters
        ----------
        ev : pg.MouseDragEvent

        """
        super().mouseClickEvent(ev)

        # Check which key is pressed
        modifierPressed = QtGui.QApplication.keyboardModifiers()

        if (ev.buttons() == QtCore.Qt.LeftButton) and ev.double():
            if (modifierPressed & QtCore.Qt.ControlModifier) == QtCore.Qt.ControlModifier:
                # Potentially, there is nothing to play !
                if self._wav is None:
                    return

                # Extract position
                start = int(self.start * self._wav[1])
                end = int(self.end * self._wav[1])

                # Play subpart
                player.play(self._wav[0][start:end])

            elif (modifierPressed & QtCore.Qt.ShiftModifier) == QtCore.Qt.ShiftModifier:
                self.parentWidget().setXRange(0, self.parentWidget().state["limits"]["xLimits"][1])
            elif (not modifierPressed):
                self.parentWidget().setXRange(self.start, self.end)


class SelectableViewBox(pg.ViewBox):
    """Viewbox with region selection support (for playback and zoom)

    Attributes
    ----------
    wav : tuple(np.array, int)
        The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

    _select : bool
        flag to indicate used to avoid conflicts between region selection and other mouse events

    _dragPoint : SegmentItem
        Handle to save the highlighted region
    """

    def __init__(self, wav=None, *args, **kwargs):
        """
        Parameters
        ----------
        wav : tuple(np.array, int), optional
            The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate. (default: None)

        args : TODO
            remaining arguments

        kwargs : keyword arguments
            Used to transmit values to pg.plotItem. *The keyword viewBox is ignored*
        """
        super().__init__(*args, **kwargs)
        self._dragPoint = None
        self._select = False
        self.wav = wav

    def mouseDragEvent(self, ev):
        """The item dragging event handler.

        It adds the creation of an highlighted region if shift is activated.

        Parameters
        ----------
        ev : pg.MouseDragEvent

        """
        # Check which key is pressed
        modifierPressed = QtGui.QApplication.keyboardModifiers()

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
            if self._dragPoint is not None:
                self._dragPoint.setRegion((start, end))
            else:
                self._dragPoint = SegmentItem(start, end, wav=self.wav)
                self.parentWidget().addItem(self._dragPoint)

            self._select = True

        # Finish
        elif ev.isFinish():
            self._select = False

        # Definition of the region in progress
        else:
            if self._dragPoint is not None:
                # Compute start position
                start_pos = ev.buttonDownPos()
                start = self.mapSceneToView(start_pos).x()

                # Compute end position
                end_pos = ev.pos()
                end = self.mapSceneToView(end_pos).x()

                # Update region
                self._dragPoint.setRegion((start, end))
            else:
                ev.ignore()
                return

        # Indicate that the event has been accepted and everything has been done
        ev.accept()
