from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pyqtgraph.GraphicsScene.mouseEvents import HoverEvent, MouseClickEvent

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from pyqtgraph.dockarea import Dock

from spiny.gui.items import SegmentItem
from .model import Annotation, AnnotationSet
from spiny.core import player


class AnnotationDock(Dock):
    """Dock containing annotation informations

    Attributes
    ----------
    annotation: spiny.annotation.AnnotationLoader
        The annotation loader object

    """

    def __init__(self, name: str, size: tuple[int, int], wav_plot: pg.PlotWidget) -> None:
        """
        Parameters
        ----------
        size : type
            description

        annotation: spiny.annotation.AnnotationLoader
            The annotation loader object

        """
        Dock.__init__(self, name=name, size=size)

        self.startPos = None

        # Define some attributes
        self._wav_plot = wav_plot

        # Prepare scrolling support
        self.scroll = QtWidgets.QScrollArea()
        self.widget = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.setContentsMargins(0, 0, 0, 0)

        self.widget.setLayout(self.vbox)
        self.addWidget(self.scroll)

        self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.widget)

        self._tiers_dict: dict[str, TierPlot] = dict()

        self._model: AnnotationSet | None = None

    def setModel(self, model: AnnotationSet, handle_edit_segment: Callable[[AnnotationItem | None], None]) -> None:
        """Define the annotations to render and render them

        Parameters
        ----------
        model : spiny.annotations.model.AnnotationSet
            The annotation set
        handle_edit_segment : callable
            Function called with the annotation item to select (or None to clear the selection)
        """
        self._model = model
        self._handle_segment = handle_edit_segment
        self.plotAnnotation()

    def plotAnnotation(self) -> None:
        """Helper to render the annotations"""
        if self._model is None:
            return

        T_max = player.duration
        for k in self._model.annotations:
            # NOTE: hidden (ignored) tiers are built too, only hidden, so that they can be shown again
            annotation_plot = TierPlot(
                name="%s_%s" % (self.name(), k), tier_name=k, model=self._model, handle_segment=self._handle_segment
            )
            annotation_plot.getAxis("left").setLabel(k)

            if len(self._model.annotations[k]) > 0:
                if T_max < self._model.annotations[k][-1].end_time:
                    T_max = self._model.annotations[k][-1].end_time

            self.vbox.addWidget(annotation_plot)
            annotation_plot.setVisible(k not in self._model.ignored)
            self._tiers_dict[k] = annotation_plot

        # Link axes
        for i in range(self.vbox.count()):
            w = self.vbox.itemAt(i).widget()
            w.setMouseEnabled(x=True, y=False)
            w.hideAxis("bottom")
            w.setLimits(
                xMin=0,
                xMax=T_max,
                yMin=0,
                yMax=1,
            )
            w.setXLink(self._wav_plot)
            w.getAxis("left").setTicks([])
            w.getAxis("left").setWidth(50)  # the same width in every dock, so that the time axes line up

    @property
    def tiers_dict(self) -> dict[str, TierPlot]:
        """dict: The tier plots, by tier name"""
        return self._tiers_dict

    def clear(self) -> None:
        """Remove every tier plot from the dock"""
        for i in reversed(range(self.vbox.count())):
            self.vbox.itemAt(i).widget().setParent(None)
        self._tiers_dict.clear()


class TierPlot(pg.PlotWidget):
    """Plot rendering one annotation tier

    Only the annotations which are visible and wide enough (see `threshold`) are rendered, see
    `updateVisibleRegions`. Clicking twice in an empty area creates a new annotation between the two
    clicks, and the Delete key removes the selected annotation.

    Parameters
    ----------
    args : list
        Positional arguments passed to pg.PlotWidget
    tier_name : str
        The name of the tier in the model
    model : spiny.annotations.model.AnnotationSet
        The annotation set containing the tier
    handle_segment : callable
        Function called with the annotation item to select (or None to clear the selection)
    kwargs : keyword arguments
        Keyword arguments passed to pg.PlotWidget

    Attributes
    ----------
    threshold : float
        The minimum width, in pixels, of a rendered annotation
    """

    def __init__(
        self,
        *args: Any,
        tier_name: str = "",
        model: AnnotationSet | None = None,
        handle_segment: Callable[[AnnotationItem | None], None],
        **kwargs: Any,
    ) -> None:
        assert model is not None
        super().__init__(*args, **kwargs)
        self.getViewBox().setBackgroundColor((0, 0, 0, 25))  # light shade, to tell the tiers apart
        self._tier_name = tier_name
        self._model = model
        self._handle_segment = handle_segment
        self.scene().sigMouseClicked.connect(self.mouse_clicked)
        self._start_pos = None

        self.threshold = 50  # minimum width (pixels) of a drawn annotation: narrower ones would be unreadable

        # Rendered items, keyed by the id() of the annotation they display
        self._items: dict[int, AnnotationItem] = dict()

        # Initial rendering
        self.updateVisibleRegions()

        # Connect the rangeChanged signal to update visible regions
        self.getPlotItem().getViewBox().sigXRangeChanged.connect(self.updateVisibleRegions)

    @property
    def annotation_items(self) -> list[AnnotationItem]:
        """The annotation items currently rendered"""
        return list(self._items.values())

    def updateVisibleRegions(self) -> None:
        """Reconcile the rendered items with the model for the current view

        Only the missing items are created and only the items which are not visible (or too small)
        anymore are removed, so that the selected item and the items created by the user survive
        panning and zooming.
        """
        # Get the current visible range
        vb = self.getPlotItem().getViewBox()
        x_min, x_max = vb.viewRange()[0]

        # Minimum duration of a drawn region: the pixel threshold converted once to seconds
        # (instead of mapping both ends of every annotation to the scene)
        min_duration = self.threshold * (x_max - x_min) / max(vb.width(), 1.0)

        # Check which regions are visible and meet the size threshold
        visible = {
            id(an): an
            for an in self._model.annotations[self._tier_name]
            if an.end_time >= x_min and an.start_time <= x_max and an.end_time - an.start_time >= min_duration
        }

        # Remove the items which are not visible anymore (the selected one is kept alive)
        for key in list(self._items.keys()):
            if (key not in visible) and (not self._items[key].isSelected()):
                self.removeItem(self._items.pop(key))

        # Add the newly visible ones
        for key, an in visible.items():
            if key not in self._items:
                region = AnnotationItem(an, showLabel=True, handle_edit=self._handle_segment)
                self.addItem(region)
                self._items[key] = region

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Delete the selected annotation on Delete, otherwise use the default behaviour

        Parameters
        ----------
        event : QtGui.QKeyEvent
            The key event
        """
        if event.key() == QtCore.Qt.Key_Delete:
            self.deleteSelectedAnnotation()
        else:
            super().keyPressEvent(event)

    def deleteSelectedAnnotation(self) -> None:
        """Remove the selected annotation of this tier (if any) from the view and from the model"""
        selected = [key for key, item in self._items.items() if item.isSelected()]
        if not selected:
            return
        item = self._items.pop(selected[0])

        # Clear the selection first so that the controller does not keep a reference to a deleted item
        self._handle_segment(None)
        self.removeItem(item)

        # Delete annotation from model (by identity: two annotations can be equal)
        tier = self._model.annotations[self._tier_name]
        for i, an in enumerate(tier):
            if an is item._segment:
                del tier[i]
                break

    def mouse_clicked(self, ev: MouseClickEvent) -> None:
        """Create an annotation from two successive clicks in an empty area of the tier

        Parameters
        ----------
        ev : pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent
            The click event
        """
        is_void = True
        items = self.scene().items(ev.scenePos())
        for x in items:
            if isinstance(x, AnnotationItem):
                is_void = False
                break

        if is_void:
            ev.accept()
            if self._start_pos is None:
                self._start_pos = ev.pos()
            else:
                # Build the annotation
                vb = self.getViewBox()
                start_time = vb.mapToView(self._start_pos).x()
                end_time = vb.mapToView(ev.pos()).x()
                if end_time < start_time:
                    tmp = start_time
                    start_time = end_time
                    end_time = tmp
                annotation = Annotation(start_time=start_time, end_time=end_time, label="")

                # Update the model
                if self._tier_name not in self._model.annotations:
                    self._model.annotations[self._tier_name] = []
                self._model.annotations[self._tier_name].append(annotation)
                self._model.annotations[self._tier_name].sort(key=lambda x: x.start_time)

                # Now add the item
                an_item = AnnotationItem(annotation, True, self._handle_segment)
                self.addItem(an_item)
                self._items[id(annotation)] = an_item
                an_item.requestSelection()
                self._start_pos = None


class AnnotationItem(SegmentItem):
    """Item to visualize an annotation.

    An annotation is a segment with a label

    Attributes
    ----------
    label : str
        The label of the annotation

    """

    _segment: Annotation  # NOTE: an annotation item always renders an Annotation (a labelled Segment)

    def __init__(
        self,
        annotation: Annotation,
        showLabel: bool = True,
        handle_edit: Callable[[AnnotationItem | None], None] | None = None,
    ) -> None:
        """
        Parameters
        ----------
        annotation : spiny.annotations.model.Annotation
            the annotation to render (it is modified in place when the item is moved or edited)

        showLabel : bool, optional
            Show the label (or not). (default: True)

        handle_edit : callable, optional
            Function called with the item to select (or None to clear the selection); without it the
            item cannot be selected. (default: None)
        """
        super().__init__(annotation, movable=True)

        self._selected = False
        self._previous_annotation_item = None
        self._next_annotation_item = None
        self._handle_edit = handle_edit

        # Some adaptations
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255, 255))
        self.setBrush(brush)
        self._default_brush = brush
        hover_brush = QtGui.QBrush(QtGui.QColor(0, 0, 255, 100))
        self.setHoverBrush(hover_brush)

        # Add label
        if showLabel:
            self._text = pg.TextItem(
                text=self._segment.label,
                anchor=(0.5, 0.5),
                color=QtWidgets.QApplication.instance().palette().color(QtGui.QPalette.Text),
            )
            self._text.setPos((self._segment.start_time + self._segment.end_time) / 2, 0.5)
            self._text.setParentItem(self)

    def hoverEvent(self, ev: HoverEvent) -> None:
        """Override hoverEvent to relax some conditions

        Parameters
        ----------
        ev : MouseHoverEvent
            the mouse hover event
        """

        if (not ev.isExit()) and ev.acceptDrags(QtCore.Qt.LeftButton):
            self.setMouseHover(True)
        else:
            self.setMouseHover(False)

    def _update_bounds(self, ev: pg.LinearRegionItem) -> None:
        """Update the segment from the lines and move the label to the middle of the segment

        Parameters
        ----------
        ev : AnnotationItem
            The item whose region changed (sent by sigRegionChangeFinished)
        """
        super()._update_bounds(ev)
        self._text.setPos((self._segment.start_time + self._segment.end_time) / 2, 0.5)

    def mouseClickEvent(self, ev: MouseClickEvent) -> None:
        """The click event handler.

        Parameters
        ----------
        ev : pg.QMouseEvent

        """
        # NOTE: deliberately skip SegmentItem.mouseClickEvent (its Shift+double-click "remove the segment"
        #       only makes sense in a SelectableViewBox); naming the class explicitly keeps this correct for subclasses
        pg.LinearRegionItem.mouseClickEvent(self, ev)

        # Check which key is pressed
        modifier_pressed = ev.modifiers()

        if (ev.buttons() == QtCore.Qt.LeftButton) and ev.double():
            if modifier_pressed == QtCore.Qt.KeyboardModifier.ControlModifier:
                ev.accept()
                player.play(start=self._segment.start_time, end=self._segment.end_time)
            elif (modifier_pressed == QtCore.Qt.KeyboardModifier.NoModifier) and self._is_zoomed_in:
                ev.accept()
                self.parentWidget().setXRange(0, self.parentWidget().state["limits"]["xLimits"][1])
                self._is_zoomed_in = not self._is_zoomed_in
            elif modifier_pressed == QtCore.Qt.KeyboardModifier.NoModifier:
                ev.accept()
                self.parentWidget().setXRange(self._segment.start_time, self._segment.end_time)
                self._is_zoomed_in = not self._is_zoomed_in

        elif (ev.buttons() == QtCore.Qt.LeftButton) and (not ev.double()):
            ev.accept()
            self.requestSelection()

    def requestSelection(self) -> None:
        """Ask the controller to make this item the current annotation (or to unselect it if it already is)

        The controller is the only owner of the selection: it calls setSelectedState() on the
        previous and the new current items.
        """
        if self._handle_edit is None:
            return
        self._handle_edit(None if self._selected else self)

    def setSelectedState(self, selected: bool) -> None:
        """Update the visual selection state (does not notify the controller)"""
        self._selected = selected
        if selected:
            self.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 50)))
        else:
            self.setBrush(self._default_brush)
        self.update()

    def updateLabel(self, label: str) -> None:
        """Change the label of the annotation

        Parameters
        ----------
        label : str
            The new label
        """
        self._segment.label = label
        self._text.setText(label)
        self._text.setPos((self._segment.start_time + self._segment.end_time) / 2, 0.5)

    def setBounds(self, start_time: float, end_time: float) -> None:
        """Move the boundaries of the annotation

        Parameters
        ----------
        start_time : float
            The new start time in seconds
        end_time : float
            The new end time in seconds
        """
        self._segment.start_time = start_time
        self.lines[0].setPos(self._segment.start_time)
        self._segment.end_time = end_time
        self.lines[1].setPos(self._segment.end_time)
        self._text.setPos((self._segment.start_time + self._segment.end_time) / 2, 0.5)

    def isSelected(self) -> bool:
        """Indicate if the annotation is the current (selected) one

        Returns
        -------
        bool
            True if the annotation is selected
        """
        return self._selected
