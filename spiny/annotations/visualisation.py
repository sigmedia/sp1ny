import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from pyqtgraph.dockarea import Dock

from spiny.gui.items import SegmentItem
from .model import Annotation
from spiny.core import player


class AnnotationDock(Dock):
    """Dock containing annotation informations

    Attributes
    ----------
    annotation: spiny.annotation.AnnotationLoader
        The annotation loader object

    """

    def __init__(self, name, size, wav_plot):
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

        self._tiers_dict = dict()

        self._model = None

    def setModel(self, model, handle_edit_segment):
        self._model = model
        self._handle_segment = handle_edit_segment
        self.plotAnnotation()

    def plotAnnotation(self):
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

            # NOTE: this is kept for record (but will be removed when the tierplot will be finalised)
            # previous_annotation = None
            # for i, elt in enumerate(self._model.annotations[k]):
            #     # Generate region item
            #     seg = AnnotationItem(elt, handle_edit=self._handle_segment)
            #     seg._previous_annotation_item = previous_annotation
            #     if previous_annotation is not None:
            #         previous_annotation._next_annotation_item = seg
            #     annotation_plot.addItem(seg)

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
            w.getAxis("left").setWidth(50)  # FIXME: hardcoded

    @property
    def tiers_dict(self):
        return self._tiers_dict

    def clear(self):
        for i in reversed(range(self.vbox.count())):
            self.vbox.itemAt(i).widget().setParent(None)
        self._tiers_dict.clear()


class TierPlot(pg.PlotWidget):
    def __init__(self, *args, tier_name="", model=None, handle_segment, **kwargs):
        assert model is not None
        super().__init__(*args, **kwargs)
        self.getViewBox().setBackgroundColor((0, 0, 0, 25))  # FIXME: harcoded
        self._tier_name = tier_name
        self._model = model
        self._handle_segment = handle_segment
        self.scene().sigMouseClicked.connect(self.mouse_clicked)
        self._start_pos = None

        self.threshold = 50  # FIXME: hardcoded threshold  # Minimum size in pixels for region to be drawn

        # Rendered items, keyed by the id() of the annotation they display
        self._items = dict()

        # Initial rendering
        self.updateVisibleRegions()

        # Connect the rangeChanged signal to update visible regions
        self.getPlotItem().getViewBox().sigXRangeChanged.connect(self.updateVisibleRegions)

    @property
    def annotation_items(self):
        """The annotation items currently rendered"""
        return list(self._items.values())

    def updateVisibleRegions(self):
        """Reconcile the rendered items with the model for the current view

        Only the missing items are created and only the items which are not visible (or too small)
        anymore are removed, so that the selected item and the items created by the user survive
        panning and zooming.
        """
        # Get the current visible range
        vb = self.getPlotItem().getViewBox()
        x_min, x_max = vb.viewRange()[0]

        # Check which regions are visible and meet the size threshold
        visible = dict()
        for an in self._model.annotations[self._tier_name]:
            if an.end_time >= x_min and an.start_time <= x_max:  # Check if within visible range
                region_width = (
                    vb.mapViewToScene(pg.Point(an.end_time, 0)).x() - vb.mapViewToScene(pg.Point(an.start_time, 0)).x()
                )
                if region_width >= self.threshold:  # Check if region is above the size threshold
                    visible[id(an)] = an

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

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            self.deleteSelectedAnnotation()
        else:
            super().keyPressEvent(event)

    def deleteSelectedAnnotation(self):
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

    def mouse_clicked(self, ev):
        # if (event.modifiers() & QtCore.Qt.ControlModifier) and
        # (event.button() == QtCore.Qt.LeftButton):

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

    def __init__(self, annotation, showLabel=True, handle_edit=None):
        """
        Parameters
        ----------
        seg_infos : tuple(float, float, str)
            the segment information (start, end, label)

        wav : tuple(np.array, int), optional
            The signal information as loaded using librosa.
            The tuple contain an array of samples and the sample rate. (default: None)

        showLabel : bool, optional
            Show the label (or not). (default: True)
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

    def hoverEvent(self, ev):
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

    def _update_bounds(self, ev):
        super()._update_bounds(ev)
        self._text.setPos((self._segment.start_time + self._segment.end_time) / 2, 0.5)

    def mouseClickEvent(self, ev):
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

    def requestSelection(self):
        """Ask the controller to make this item the current annotation (or to unselect it if it already is)

        The controller is the only owner of the selection: it calls setSelectedState() on the
        previous and the new current items.
        """
        if self._handle_edit is None:
            return
        self._handle_edit(None if self._selected else self)

    def setSelectedState(self, selected):
        """Update the visual selection state (does not notify the controller)"""
        self._selected = selected
        if selected:
            self.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 50)))
        else:
            self.setBrush(self._default_brush)
        self.update()

    def updateLabel(self, label):
        self._segment.label = label
        self._text.setText(label)
        self._text.setPos((self._segment.start_time + self._segment.end_time) / 2, 0.5)

    def setBounds(self, start_time, end_time):
        self._segment.start_time = start_time
        self.lines[0].setPos(self._segment.start_time)
        self._segment.end_time = end_time
        self.lines[1].setPos(self._segment.end_time)
        self._text.setPos((self._segment.start_time + self._segment.end_time) / 2, 0.5)

    def isSelected(self):
        return self._selected
