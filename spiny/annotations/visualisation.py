from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from pyqtgraph.GraphicsScene.mouseEvents import HoverEvent, MouseClickEvent

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from pyqtgraph.dockarea import Dock

from spiny.gui import theme
from spiny.gui.items import PlayheadLine, SegmentItem, WheelViewBox
from spiny.gui.shortcuts import shortcut
from .model import Annotation, AnnotationSet, display_label
from spiny.core import player

#: Two boundaries closer than this, in seconds, are aligned
ALIGNMENT_TOLERANCE = 0.001


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

    def setModel(
        self,
        model: AnnotationSet,
        handle_edit_segment: Callable[[AnnotationItem | None], None],
        handle_changed: Callable[[], None] | None = None,
        handle_label: Callable[[str, int], None] | None = None,
    ) -> None:
        """Define the annotations to render and render them

        Parameters
        ----------
        model : spiny.annotations.model.AnnotationSet
            The annotation set
        handle_edit_segment : callable
            Function called with the annotation item to select (or None to clear the selection)
        handle_changed : callable, optional
            Function called when an operation on the annotations has ended. (default: None)
        handle_label : callable, optional
            Function called with the label typed on the selected annotation and the position of the cursor in it.
            (default: None)
        """
        self._model = model
        self._handle_segment = handle_edit_segment
        self._handle_changed = handle_changed
        self._handle_label = handle_label
        self.plotAnnotation()

    def plotAnnotation(self) -> None:
        """Helper to render the annotations"""
        if self._model is None:
            return

        T_max = player.duration
        for k in self._model.annotations:
            # NOTE: hidden (ignored) tiers are built too, only hidden, so that they can be shown again
            annotation_plot = TierPlot(
                name="%s_%s" % (self.name(), k),
                tier_name=k,
                model=self._model,
                handle_segment=self._handle_segment,
                handle_moves=partial(self.moveAlignedBoundaries, k),
                handle_changed=self._handle_changed,
                handle_label=self._handle_label,
            )
            annotation_plot.getAxis("left").setLabel(k)

            if len(self._model.annotations[k]) > 0:
                if T_max < self._model.annotations[k][-1].end_time:
                    T_max = self._model.annotations[k][-1].end_time

            self.vbox.addWidget(annotation_plot)
            annotation_plot.setVisible(k not in self._model.ignored)
            self._tiers_dict[k] = annotation_plot

        # Link axes
        # NOTE: not through vbox.itemAt: PySide keeps the wrapper of the layout item after Qt has deleted the item,
        #       and a new Qt object at the same address is then returned as that stale wrapper
        for w in self._tiers_dict.values():
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
    def waveform_selection(self) -> tuple[float, float] | None:
        """tuple(float, float) or None: The (start, end) times of the region selected on the waveform, if any"""
        region = self._wav_plot.getViewBox()._dragPoint
        return None if region is None else (region._segment.start_time, region._segment.end_time)

    @property
    def tiers_dict(self) -> dict[str, TierPlot]:
        """dict: The tier plots, by tier name"""
        return self._tiers_dict

    def moveAlignedBoundaries(self, tier_name: str, moves: list[tuple[float, float]]) -> None:
        """Follow in the other locked tiers what has been moved in a locked tier

        Parameters
        ----------
        tier_name : str
            The tier where the boundaries have been moved
        moves : list(tuple(float, float))
            The (old, new) times of the boundaries which have been moved
        """
        if self._model is not None and tier_name in self._model.locked:
            for other in self._model.locked - {tier_name}:
                self._tiers_dict[other].moveBoundaries(moves)

    def clear(self) -> None:
        """Remove every tier plot from the dock and destroy it"""
        for tier_plot in self._tiers_dict.values():
            self.vbox.removeWidget(tier_plot)
            tier_plot.hide()
            tier_plot.deleteLater()
        self._tiers_dict.clear()


class TierPlot(pg.PlotWidget):
    """Plot rendering one annotation tier

    Only the annotations which are visible and wide enough (see `threshold`) are rendered, see
    `updateVisibleRegions`. Clicking in an empty area moves the playhead, clicking twice creates a new annotation
    between the two clicks, and the Delete key removes the selected annotation. The label of the selected annotation
    can be typed on it, in a text field placed over it (see `editLabel`).

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
    handle_moves : callable, optional
        Function called with the (old, new) times of the boundaries which have been moved
    handle_changed : callable, optional
        Function called when an operation on the annotations has ended
    handle_label : callable, optional
        Function called with the label typed on the selected annotation and the position of the cursor in it
    kwargs : keyword arguments
        Keyword arguments passed to pg.PlotWidget

    Attributes
    ----------
    threshold : float
        The minimum width, in pixels, of a rendered annotation
    """

    #: The minimum width, in pixels, of the text field of the label: it is hidden on a narrower annotation
    MIN_EDITOR_WIDTH = 36

    def __init__(
        self,
        *args: Any,
        tier_name: str = "",
        model: AnnotationSet | None = None,
        handle_segment: Callable[[AnnotationItem | None], None],
        handle_moves: Callable[[list[tuple[float, float]]], None] | None = None,
        handle_changed: Callable[[], None] | None = None,
        handle_label: Callable[[str, int], None] | None = None,
        **kwargs: Any,
    ) -> None:
        assert model is not None
        super().__init__(*args, viewBox=WheelViewBox(), **kwargs)
        self._tier_name = tier_name
        self._model = model
        self._handle_segment = handle_segment
        self._handle_moves = handle_moves
        self._handle_changed = handle_changed
        self._handle_label = handle_label

        # While its label is edited, the selected annotation shows it in this field, placed over the annotation
        self._editing = False
        self._editor = QtWidgets.QLineEdit(self.viewport())
        self._editor.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._editor.hide()
        self._editor.textEdited.connect(self._onLabelTyped)
        self._editor.cursorPositionChanged.connect(self._onLabelTyped)
        self._editor.textChanged.connect(self.placeEditor)
        self._editor.editingFinished.connect(self._endEdition)  # Enter, or the keyboard going elsewhere
        self.getViewBox().sigResized.connect(self.placeEditor)
        self.applyTheme()
        self.scene().sigMouseClicked.connect(self.mouse_clicked)
        self._start_time: float | None = None

        self.addItem(PlayheadLine(), ignoreBounds=True)
        self.threshold = 50  # minimum width (pixels) of a drawn annotation: narrower ones would be unreadable

        # Rendered items, keyed by the id() of the annotation they display
        self._items: dict[int, AnnotationItem] = dict()

        # Initial rendering
        self.updateVisibleRegions()

        # Connect the rangeChanged signal to update visible regions
        self.getPlotItem().getViewBox().sigXRangeChanged.connect(self.updateVisibleRegions)

    def applyTheme(self) -> None:
        """Shade the background with the colour of the current theme, to tell the tiers and the locked ones apart"""
        locked = self._tier_name in self._model.locked
        self.getViewBox().setBackgroundColor(theme.color("tier_locked" if locked else "tier_background"))
        text_color = theme.color("annotation_text").name()
        self._editor.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; border-bottom: 1px solid {text_color};"
            f" color: {text_color}; }}"
        )

    def addAnnotation(self, start_time: float, end_time: float) -> None:
        """Add an empty annotation to the tier and select it

        Parameters
        ----------
        start_time : float
            The start of the annotation, in seconds
        end_time : float
            The end of the annotation, in seconds
        """
        annotation = Annotation(start_time=start_time, end_time=end_time, label="")
        self._model.annotations.setdefault(self._tier_name, []).append(annotation)
        self._model.annotations[self._tier_name].sort(key=lambda x: x.start_time)

        item = self._createItem(annotation)
        self._items[id(annotation)] = item
        item.requestSelection()
        self._notifyChanged()

    def _createItem(self, annotation: Annotation) -> AnnotationItem:
        """Draw an annotation

        Parameters
        ----------
        annotation : Annotation
            The annotation

        Returns
        -------
        AnnotationItem
            The item, already in the plot
        """
        item = AnnotationItem(annotation, True, self._handle_segment, self._handle_moves)
        item.sigRegionChangeFinished.connect(self._notifyChanged)
        self.addItem(item)
        return item

    def _notifyChanged(self, *args: Any) -> None:
        """Report the end of an operation on the annotations

        Parameters
        ----------
        args : list
            The arguments of the signal (unused)
        """
        if self._handle_changed is not None:
            self._handle_changed()

    def moveBoundaries(self, moves: list[tuple[float, float]]) -> None:
        """Move the boundaries of this tier which are aligned with moved ones

        A change which would leave an annotation with no duration is not applied to it.

        Parameters
        ----------
        moves : list(tuple(float, float))
            The (old, new) times of the boundaries which have been moved
        """

        def moved(time: float) -> float:
            return next((new for old, new in moves if abs(time - old) <= ALIGNMENT_TOLERANCE), time)

        for annotation in self._model.annotations[self._tier_name]:
            start_time, end_time = moved(annotation.start_time), moved(annotation.end_time)
            changed = (start_time, end_time) != (annotation.start_time, annotation.end_time)
            if changed and start_time < end_time:
                item = self._items.get(id(annotation))
                if item is not None:
                    item.setBounds(start_time, end_time)
                else:
                    annotation.start_time, annotation.end_time = start_time, end_time

    def _onLabelTyped(self, *args: Any) -> None:
        """Report the label typed on the selected annotation, and where its cursor is

        Parameters
        ----------
        args : list
            The arguments of the signal (unused)
        """
        # NOTE: only what is typed here: the field also follows the label typed in the control panel
        if self._handle_label is not None and self._editor.hasFocus():
            self._handle_label(self._editor.text(), self._editor.cursorPosition())

    def editLabel(self) -> None:
        """Type the label of the selected annotation of this tier on the annotation itself

        The text field has the keyboard until Enter: the one-key shortcuts (of the player, for instance) are typed.
        """
        self._editing = True
        self.placeEditor()
        self._editor.setFocus()  # NOTE: nothing happens if the field could not be shown

    def _endEdition(self) -> None:
        """Leave the edition of the label: the keyboard is back to the shortcuts"""
        self._editing = False
        self.placeEditor()
        self._notifyChanged()

    def placeEditor(self, *args: Any) -> None:
        """Put the text field over the selected annotation while its label is edited, otherwise hide it

        The field is as wide as its text, in the middle of the visible part of the annotation: the rest of the
        annotation still gets the clicks (selection, zoom, move). The edition ends if the annotation is not selected
        anymore, or if it leaves the view.

        Parameters
        ----------
        args : list
            The arguments of the signal (unused)
        """
        editor = self._editor
        item = next((item for item in self._items.values() if item.isSelected()), None)
        view = self.mapFromScene(self.getViewBox().sceneBoundingRect()).boundingRect()
        left, right = view.left(), view.left() - 1
        if item is not None:
            start, end = (self.getViewBox().mapViewToScene(QtCore.QPointF(time, 0)) for time in item.getRegion())
            left = max(self.mapFromScene(start).x(), view.left())
            right = min(self.mapFromScene(end).x(), view.right())

        self._editing = self._editing and item is not None and right - left >= self.MIN_EDITOR_WIDTH
        if item is not None:
            item.setLabelVisible(not self._editing)
        if not self._editing:
            if editor.hasFocus():
                self.setFocus()  # NOTE: otherwise Qt gives the keyboard to another text field
            editor.hide()
            return

        assert item is not None
        label = item._segment.label
        if editor.isHidden():
            editor.setText(label)
        elif editor.text() != label:
            # The label was changed from the control panel: the cursor stays after what has been inserted
            position = editor.cursorPosition() + len(label) - len(editor.text())
            editor.setText(label)
            editor.setCursorPosition(max(position, 0))
        text_width = editor.fontMetrics().horizontalAdvance(label) + 2 * self.MIN_EDITOR_WIDTH // 3
        width = min(max(text_width, self.MIN_EDITOR_WIDTH), right - left - 8)
        height = editor.sizeHint().height()
        editor.setGeometry((left + right - width) // 2, view.center().y() - height // 2, width, height)
        editor.show()

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
                self._items[key] = self._createItem(an)
        self.placeEditor()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Delete the selected annotation on its shortcut, otherwise use the default behaviour

        Parameters
        ----------
        event : QtGui.QKeyEvent
            The key event
        """
        if QtGui.QKeySequence(event.keyCombination()) == shortcut("delete_annotation"):
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
        self._notifyChanged()

    def mouse_clicked(self, ev: MouseClickEvent) -> None:
        """Move the playhead to a left click in an empty area of the tier; two of them create an annotation

        With the Shift key, the playhead (and so a playback) is left alone. A double-click or a click on an
        annotation cancels the first click.

        Parameters
        ----------
        ev : pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent
            The click event
        """
        vb = self.getViewBox()
        if ev.button() != QtCore.Qt.MouseButton.LeftButton or not vb.sceneBoundingRect().contains(ev.scenePos()):
            return

        on_annotation = any(isinstance(item, AnnotationItem) for item in self.scene().items(ev.scenePos()))
        if on_annotation or ev.double():
            self._start_time = None
            return

        ev.accept()
        # NOTE: a time and not a position: the view can change before the second click
        time = vb.mapSceneToView(ev.scenePos()).x()
        if not ev.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier:  # with Shift, the click only creates
            player.seek(time)
        if self._start_time is None:
            self._start_time = time
            return

        start_time, end_time = sorted((self._start_time, time))
        self._start_time = None
        if start_time == end_time:
            return
        self.addAnnotation(start_time, end_time)


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
        handle_moves: Callable[[list[tuple[float, float]]], None] | None = None,
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

        handle_moves : callable, optional
            Function called with the (old, new) times of the boundaries which have been moved. (default: None)
        """
        super().__init__(annotation, movable=True)

        self._selected = False
        self._previous_annotation_item = None
        self._next_annotation_item = None
        self._handle_edit = handle_edit
        self._handle_moves = handle_moves
        self.sigRegionChanged.connect(self._onRegionChanged)

        # Add label
        self._text: Any = None
        if showLabel:
            self._text = pg.TextItem(text=display_label(self._segment.label), anchor=(0.5, 0.5))
            self._text.setPos((self._segment.start_time + self._segment.end_time) / 2, 0.5)
            self._text.setParentItem(self)

        self.applyTheme()

    def applyTheme(self) -> None:
        """Draw the annotation with the colours of the current theme"""
        self.setBrush(QtGui.QBrush(theme.color("annotation_selected" if self._selected else "annotation")))
        self.setHoverBrush(QtGui.QBrush(theme.color("annotation_hover")))
        for line in self.lines:
            line.setPen(theme.color("annotation_border"))
        if self._text is not None:
            self._text.setColor(theme.color("annotation_text"))

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

    def _onRegionChanged(self, *args: Any) -> None:
        """Report the boundaries moved with the mouse, while they are moving

        Parameters
        ----------
        args : list
            The arguments of the signal (unused)
        """
        old_start, old_end = self._segment.start_time, self._segment.end_time
        self._segment.start_time, self._segment.end_time = self.lines[0].getXPos(), self.lines[1].getXPos()
        self.reportMoves(old_start, old_end)
        self._placeEditor()

    def reportMoves(self, old_start: float, old_end: float) -> None:
        """Tell which boundaries have moved

        Parameters
        ----------
        old_start : float
            The previous start time, in seconds
        old_end : float
            The previous end time, in seconds
        """
        pairs = ((old_start, self._segment.start_time), (old_end, self._segment.end_time))
        moves = [(old, new) for old, new in pairs if old != new]
        if moves and self._handle_moves is not None:
            self._handle_moves(moves)

    def _update_bounds(self, ev: pg.LinearRegionItem) -> None:
        """Update the segment from the lines and move the label to the middle of the segment

        Parameters
        ----------
        ev : AnnotationItem
            The item whose region changed (sent by sigRegionChangeFinished)
        """
        self._onRegionChanged()  # NOTE: the last step of a drag only comes with the signal of the end of the drag
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
            elif modifier_pressed == QtCore.Qt.KeyboardModifier.NoModifier:
                ev.accept()
                self.toggleZoom()

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
        self.applyTheme()
        self.update()
        self.setLabelVisible(True)
        self._placeEditor()

    def setLabelVisible(self, visible: bool) -> None:
        """Show or hide the label: it is hidden while it is edited in the text field of the tier

        Parameters
        ----------
        visible : bool
            True to show the label
        """
        if self._text is not None:
            self._text.setVisible(visible)

    def _placeEditor(self) -> None:
        """Tell the tier that the text field of the label must follow this annotation"""
        tier = self.getViewWidget()
        if isinstance(tier, TierPlot):
            tier.placeEditor()

    def updateLabel(self, label: str) -> None:
        """Change the label of the annotation

        Parameters
        ----------
        label : str
            The new label
        """
        self._segment.label = label
        self._text.setText(display_label(label))
        self._text.setPos((self._segment.start_time + self._segment.end_time) / 2, 0.5)
        self._placeEditor()

    def setBounds(self, start_time: float, end_time: float) -> None:
        """Move the boundaries of the annotation

        Parameters
        ----------
        start_time : float
            The new start time in seconds
        end_time : float
            The new end time in seconds
        """
        self._segment.start_time, self._segment.end_time = start_time, end_time
        # NOTE: blocked: this is not a move of the user, and the lines must not be sorted when they cross on the way
        self.blockLineSignal = True
        self.lines[0].setPos(start_time)
        self.lines[1].setPos(end_time)
        self.blockLineSignal = False
        self.prepareGeometryChange()
        self.update()
        self._text.setPos((self._segment.start_time + self._segment.end_time) / 2, 0.5)
        self._placeEditor()

    def isSelected(self) -> bool:
        """Indicate if the annotation is the current (selected) one

        Returns
        -------
        bool
            True if the annotation is selected
        """
        return self._selected
