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

        T_max = player._wav.shape[0] / player._sampling_rate
        for k in self._model.annotations:
            if k in self._model.ignored:
                continue

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


class TierPlot(pg.PlotWidget):
    keyPressed = QtCore.Signal(QtCore.QEvent)

    def __init__(self, *args, tier_name="", model=None, handle_segment, **kwargs):
        assert model is not None
        super().__init__(*args, **kwargs)
        self.getViewBox().setBackgroundColor((0, 0, 0, 25)) # FIXME: harcoded
        self._tier_name = tier_name
        self._model = model
        self._handle_segment = handle_segment
        self.keyPressed.connect(self.on_key)
        self.scene().sigMouseClicked.connect(self.mouse_clicked)
        self._start_pos = None

        self.threshold = 50 # FIXME: hardcoded threshold  # Minimum size in pixels for region to be drawn
        self.linear_regions = []

        # Initial rendering
        self.updateVisibleRegions()

        # Connect the rangeChanged signal to update visible regions
        self.getPlotItem().getViewBox().sigXRangeChanged.connect(self.updateVisibleRegions)

    def updateVisibleRegions(self):
        # Clear previous regions
        for region in self.linear_regions:
            self.removeItem(region)
        self.linear_regions.clear()

        # Get the current visible range
        view_range = self.getPlotItem().getViewBox().viewRange()
        x_min, x_max = view_range[0]

        # Check which regions are visible and meet the size threshold
        tier = self._model.annotations[self._tier_name]
        for an in tier:
            start = an.start_time
            end = an.end_time

            if end >= x_min and start <= x_max:  # Check if within visible range
                region_width = self.getPlotItem().vb.mapViewToScene(pg.Point(end, 0)).x() - \
                               self.getPlotItem().vb.mapViewToScene(pg.Point(start, 0)).x()
                if region_width >= self.threshold:  # Check if region is above the size threshold
                    region = AnnotationItem(an, showLabel=True)
                    self.addItem(region)
                    self.linear_regions.append(region)

    def keyPressEvent(self, event):
        super(TierPlot, self).keyPressEvent(event)
        self.keyPressed.emit(event)

    def on_key(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            print(self._tier_name)
            handle_item = None
            # Remove item from the view
            for item in self.items():
                if item.isSelected():
                    handle_item = item
                    self.removeItem(item)
                    break

            # Delete annotation from model
            tier = self._model.annotations[self._tier_name]
            for an in tier:
                if an == handle_item._segment:
                    tier.remove(an)
                    break

        else:
            super().keyPressEvent(event)

        # if event.key() == QtCore.Qt.Key_Enter and self.ui.continueButton.isEnabled():
        #     self.proceed()  # this is called whenever the continue button is pressed
        # elif event.key() == QtCore.Qt.Key_Q:
        #     print("Killing")
        #     self.deleteLater()  # a test I implemented to see if pressing 'Q' would close the window

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
                sorted(self._model.annotations[self._tier_name], key=lambda x: x.start_time)

                # Now add the item
                an_item = AnnotationItem(annotation, True, self._handle_segment)
                self.addItem(an_item)
                an_item.select()
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
        # NOTE: bypass segment to avoid issue with "remove the segment" -> go straight to "grandpa" class
        super(type(self).__bases__[0], self).mouseClickEvent(ev)

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
            self.select()

    def select(self):
        if self._handle_edit is None:
            return

        # Toggle the selected flag
        self._selected = not self._selected

        # Update the brush
        if self._selected:
            brush = QtGui.QBrush(QtGui.QColor(255, 0, 0, 50))
            self._handle_edit(self)
        else:
            brush = self._default_brush
            self._handle_edit(None)
        self.setBrush(brush)
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
