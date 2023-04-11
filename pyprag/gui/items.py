import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from pyprag.core import player
from .tmp import RedefinedLinearRegionItem


###############################################################################
# Classes
###############################################################################
class SelectablePlotItem(pg.PlotItem):
    """PlotItem using a SelectableViewBox instead of a standard pg.ViewBox"""

    def __init__(self, lock_y_axis=False, **kwargs):
        """
        Parameters
        ----------

        kwargs : keyword arguments
            Used to transmit values to pg.plotItem. *The keyword viewBox is ignored*

        """
        vb = SelectableViewBox(lock_y_axis=lock_y_axis)
        kwargs["viewBox"] = vb
        super().__init__(**kwargs)
        vb.setParentItem(self)


class SegmentItem(RedefinedLinearRegionItem):
    """A segment item which is a specific pg.LinearRegionItem

    Attributes
    ----------
    start : float
        The start position (in seconds)

    end : float
        The end position (in seconds)

    movable : bool
        Indicate if the segment can be moved (start and end are changing)

    """

    def __init__(self, start, end, movable=False, related=[]):
        """
        Parameters
        ----------
        start : float
            The start position (in seconds)

        end : float
            The end position (in seconds)

        movable : bool
            Indicate if the segment can be moved (start and end are changing).
            (default: False)

        related : list
            List of related segments (instances of SegmentItem). (default: [])
        """
        super().__init__()

        self._related = related
        self._is_zoomed_in = True

        # Some adaptations
        brush = QtGui.QBrush(QtGui.QColor(255, 0, 0, 50))
        self.setBrush(brush)

        # Set the bounds
        self.setRegion((start, end))

        self.sigRegionChangeFinished.connect(self._update_bounds)

    def setRegion(self, bounds):
        """Set the values for the edges of the region. If related items have been specified, they are
        updated with the same bound values.

        Parameters
        ----------
        bounds : (float, float)
            the new (start, end) values

        """
        # Get segment informations
        if bounds[1] < bounds[0]:
            self.start = bounds[1]
            self.end = bounds[0]
        else:
            self.start = bounds[0]
            self.end = bounds[1]
        bounds = (self.start, self.end)

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
        ev : pg.QMouseEvent

        """
        super().mouseClickEvent(ev)

        # Check which key is pressed
        modifier_pressed = ev.modifiers()

        if (ev.buttons() == QtCore.Qt.LeftButton) and ev.double():

            if modifier_pressed == QtCore.Qt.KeyboardModifier.ControlModifier:
                player.play(start=self.start, end=self.end)
            elif modifier_pressed == QtCore.Qt.KeyboardModifier.ShiftModifier:
                self.parentWidget().removeSegment()
            elif (modifier_pressed == QtCore.Qt.KeyboardModifier.NoModifier) and self._is_zoomed_in:
                self.parentWidget().setXRange(0, self.parentWidget().state["limits"]["xLimits"][1])
                self._is_zoomed_in = not self._is_zoomed_in
            elif modifier_pressed == QtCore.Qt.KeyboardModifier.NoModifier:
                self.parentWidget().setXRange(self.start, self.end)
                self._is_zoomed_in = not self._is_zoomed_in

    def _update_bounds(self, ev):
        self.start = self.lines[0].getXPos()
        self.end = self.lines[1].getXPos()


class SelectableViewBox(pg.ViewBox):
    """Viewbox with region selection support (for playback and zoom)

    Attributes
    ----------
    wav : tuple(np.array, int)
        The signal information as loaded using librosa.
        The tuple contain an array of samples and the sample rate.

    _select : bool
        flag to indicate used to avoid conflicts between region selection and other mouse events

    _dragPoint : SegmentItem
        Handle to save the highlighted region
    """

    def __init__(self, lock_y_axis=False, *args, **kwargs):
        """
        Parameters
        ----------
        args : TODO
            remaining arguments

        kwargs : keyword arguments
            Used to transmit values to pg.plotItem. *The keyword viewBox is ignored*
        """

        super().__init__(*args, **kwargs)
        self._dragPoint = None
        self._select = False
        self._lock_y_axis = lock_y_axis

    def mouseDragEvent(self, ev):
        """The item dragging event handler.

        It adds the creation of an highlighted region if shift is activated.

        Parameters
        ----------
        ev : pg.MouseDragEvent

        """
        # Check which key is pressde
        modifier_pressed = ev.modifiers()

        # Ignore any event while selecting the region
        if not self._select:
            if modifier_pressed == QtCore.Qt.KeyboardModifier.ShiftModifier:
                super().mouseDragEvent(ev)
                return

        # Start to define the region
        if ev.isStart():
            # Compute start position
            start_pos = ev.buttonDownPos()
            start = self.mapToView(start_pos).x()

            # Compute end position
            end_pos = ev.pos()
            end = self.mapToView(end_pos).x()

            # Check
            if self._dragPoint is not None:
                self._dragPoint.setRegion((start, end))
            else:
                self._dragPoint = SegmentItem(start, end)
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
                start = self.mapToView(start_pos).x()

                # Compute end position
                end_pos = ev.pos()
                end = self.mapToView(end_pos).x()

                # Update region
                self._dragPoint.setRegion((start, end))
            else:
                ev.ignore()
                return

        # Indicate that the event has been accepted and everything has been done
        ev.accept()

    def scaleBy(self, s=None, center=None, x=None, y=None):
        """
        Scale by *s* around given center point (or center of view).
        *s* may be a pg.Point or tuple (x, y).

        Optionally, x or y may be specified individually. This allows the other
        axis to be left unaffected (note that using a scale factor of 1.0 may
        cause slight changes due to floating-point error).
        """

        if s is not None:
            x, y = s[0], s[1]

        if self._lock_y_axis:
            y = None

        affect = [x is not None, y is not None]
        if not any(affect):
            return

        scale = pg.Point([1.0 if x is None else x, 1.0 if y is None else y])

        if self.state["aspectLocked"] is not False:
            scale[0] = scale[1]

        vr = self.targetRect()
        if center is None:
            center = pg.Point(vr.center())
        else:
            center = pg.Point(center)

        tl = center + (vr.topLeft() - center) * scale
        br = center + (vr.bottomRight() - center) * scale

        if not affect[0]:
            self.setYRange(tl.y(), br.y(), padding=0)
        elif not affect[1]:
            self.setXRange(tl.x(), br.x(), padding=0)
        else:
            self.setRange(QtCore.QRectF(tl, br), padding=0)

    def removeSegment(self):
        self.parentWidget().removeItem(self._dragPoint)
        self._dragPoint = None
