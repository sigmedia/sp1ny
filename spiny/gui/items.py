from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pyqtgraph.GraphicsScene.mouseEvents import MouseClickEvent, MouseDragEvent

from typing import Optional
from spiny.core.segment import Segment
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from spiny.core import player


###############################################################################
# Classes
###############################################################################
class SelectablePlotItem(pg.PlotItem):
    """PlotItem using a SelectableViewBox instead of a standard pg.ViewBox"""

    def __init__(self, lock_y_axis: bool = False, **kwargs: Any) -> None:
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


class LinkedInfiniteLine(pg.InfiniteLine):
    """Infinite line which can be linked to another one (the link is mutual)

    Parameters
    ----------
    linked_line : LinkedInfiniteLine, optional
        The line to link to. (default: None)
    pos, angle, pen, movable, bounds, hoverPen, label, labelOpts, span, markers, name
        See pg.InfiniteLine
    """

    def __init__(
        self,
        linked_line: LinkedInfiniteLine | None = None,
        pos: Any = None,
        angle: float = 90,
        pen: Any = None,
        movable: bool = False,
        bounds: Sequence[float] | None = None,
        hoverPen: Any = None,
        label: str | None = None,
        labelOpts: dict | None = None,
        span: tuple[float, float] = (0, 1),
        markers: list | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(pos, angle, pen, movable, bounds, hoverPen, label, labelOpts, span, markers, name)

        self._linked_line = linked_line
        if linked_line is not None:
            linked_line._linked_line = self


class SegmentItem(pg.LinearRegionItem):
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

    def __init__(
        self,
        segment: Segment,
        movable: bool = True,
        related: Sequence[SegmentItem] | None = None,
        span: tuple[float, float] = (0, 1),
        swapMode: str | None = "sort",
        clipItem: pg.GraphicsObject | None = None,
        pen: Any = None,
        hoverPen: Any = None,
        bounds: Sequence[float] | None = None,
    ) -> None:
        """
        Parameters
        ----------

        movable : bool
            Indicate if the segment can be moved (start and end are changing).
            (default: False)

        related : list
            List of related segments (instances of SegmentItem). (default: None, i.e. no related segment)
        """

        pg.GraphicsObject.__init__(self)

        self._segment = segment
        self._related = list(related) if related is not None else []
        self._is_zoomed_in = False

        self.orientation = "vertical"
        self.blockLineSignal = False
        self.moving = False
        self.mouseHovering = False
        self.span = span
        self.swapMode = swapMode
        self.clipItem = clipItem

        self._boundingRectCache = None
        self._clipItemBoundsCache = None

        # note RedefinedLinearRegionItem.Horizontal and RedefinedLinearRegionItem.Vertical
        # are kept for backward compatibility.
        lineKwds = dict(
            movable=movable,
            bounds=bounds,
            span=span,
            pen=pen,
            hoverPen=hoverPen,
        )

        self.lines = [
            LinkedInfiniteLine(pos=QtCore.QPointF(self._segment.start_time, 0), angle=90, **lineKwds),
            LinkedInfiniteLine(pos=QtCore.QPointF(self._segment.end_time, 0), angle=90, **lineKwds),
        ]

        brush = QtGui.QBrush(QtGui.QColor(0, 0, 255, 50))
        self.setBrush(brush)
        hover_brush = QtGui.QBrush(QtGui.QColor(255, 0, 0, 50))
        self.setHoverBrush(hover_brush)

        self.setMovable(movable)

        # Set the bounds

        for line in self.lines:
            line.setParentItem(self)
            line.sigPositionChangeFinished.connect(self.lineMoveFinished)
        self.lines[0].sigPositionChanged.connect(self._line0Moved)
        self.lines[1].sigPositionChanged.connect(self._line1Moved)
        self.sigRegionChangeFinished.connect(self._update_bounds)

    def setRegion(self, bounds: Sequence[float]) -> None:
        """Set the values for the edges of the region. If related items have been specified, they are
        updated with the same bound values.

        Parameters
        ----------
        bounds : (float, float)
            the new (start, end) values

        """
        # Get segment informations
        if bounds[1] < bounds[0]:
            self._segment.start_time = bounds[1]
            self._segment.end_time = bounds[0]
        else:
            self._segment.start_time = bounds[0]
            self._segment.end_time = bounds[1]
        bounds = (self._segment.start_time, self._segment.end_time)

        super().setRegion(bounds)

        for s in self._related:
            s.setRegion(bounds)

    def mouseClickEvent(self, ev: MouseClickEvent) -> None:
        """The click event handler.


        Parameters
        ----------
        ev : pg.QMouseEvent

        """
        super().mouseClickEvent(ev)

        # Check which key is pressed
        modifier_pressed = ev.modifiers()

        if (ev.buttons() == QtCore.Qt.LeftButton) and ev.double():
            if modifier_pressed == QtCore.Qt.KeyboardModifier.ControlModifier:
                player.play(start=self._segment.start_time, end=self._segment.end_time)
            elif modifier_pressed == QtCore.Qt.KeyboardModifier.ShiftModifier:
                self.parentWidget().removeSegment()
            elif (modifier_pressed == QtCore.Qt.KeyboardModifier.NoModifier) and self._is_zoomed_in:
                self.parentWidget().setXRange(0, self.parentWidget().state["limits"]["xLimits"][1])
                self._is_zoomed_in = not self._is_zoomed_in
            elif modifier_pressed == QtCore.Qt.KeyboardModifier.NoModifier:
                self.parentWidget().setXRange(self._segment.start_time, self._segment.end_time)
                self._is_zoomed_in = not self._is_zoomed_in

    def _update_bounds(self, ev: pg.LinearRegionItem) -> None:
        """Update the segment from the positions of the lines

        Parameters
        ----------
        ev : SegmentItem
            The item whose region changed (sent by sigRegionChangeFinished)
        """
        self._segment.start_time = self.lines[0].getXPos()
        self._segment.end_time = self.lines[1].getXPos()


class SelectableViewBox(pg.ViewBox):
    """Viewbox with region selection support (for playback and zoom)

    Attributes
    ----------
    _select : bool
        flag to indicate used to avoid conflicts between region selection and other mouse events

    _dragPoint : SegmentItem
        Handle to save the highlighted region
    """

    def __init__(self, lock_y_axis: bool = False, *args: Any, **kwargs: Any) -> None:
        """
        Parameters
        ----------
        lock_y_axis : bool, optional
            If True, the y axis cannot be zoomed or panned with the mouse. (default: False)

        args : list
            remaining positional arguments, passed to pg.ViewBox

        kwargs : keyword arguments
            remaining keyword arguments, passed to pg.ViewBox
        """

        super().__init__(*args, **kwargs)
        self._dragPoint: Optional[SegmentItem] = None
        self._select = False

        self.setMouseEnabled(x=True, y=not lock_y_axis)
        self._lock_y_axis = lock_y_axis

    def mouseDragEvent(self, ev: MouseDragEvent) -> None:
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
                segment: Segment = Segment(start, end)
                self._dragPoint = SegmentItem(segment)
                self.parentWidget().addItem(self._dragPoint)

            self._select = True

        # Finish
        elif ev.isFinish():
            self._select = False

        # Definition of the region in progress
        elif self._dragPoint is not None:
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

    def scaleBy(
        self, s: Sequence[float] | None = None, center: Any = None, x: float | None = None, y: float | None = None
    ) -> None:
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

    def removeSegment(self) -> None:
        """Remove the highlighted region"""
        self.parentWidget().removeItem(self._dragPoint)
        self._dragPoint = None
