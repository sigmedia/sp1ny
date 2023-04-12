import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from pyqtgraph.dockarea import Dock

from pyprag.gui.items import SegmentItem
from pyprag.core import player

from .control import controller


class AnnotationDock(Dock):
    """Dock containing annotation informations

    Attributes
    ----------
    annotation: pyprag.annotation.AnnotationLoader
        The annotation loader object

    reference_plot : pg.PlotWidget
        The reference annotation tier rendering as we have a plot per tier

    """

    def __init__(self, name, size, annotation_set):
        """
        Parameters
        ----------
        size : type
            description

        annotation: pyprag.annotation.AnnotationLoader
            The annotation loader object

        """
        Dock.__init__(self, name=name, size=size)

        # Define some attributes
        self.annotation_set = annotation_set

        # Prepare scrolling support
        self.scroll = QtWidgets.QScrollArea()
        self.widget = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout()
        self.widget.setLayout(self.vbox)
        self.addWidget(self.scroll)

        self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.widget)

        # Render everything
        self.__plotAnnotation()

    def __plotAnnotation(self):
        """Helper to render the annotations"""
        wav_data = player._data
        sr = player._sampling_rate
        T_max = wav_data.shape[0] / sr
        for k in self.annotation_set.annotations:
            annotation_plot = pg.PlotWidget(name="%s_%s" % (self.name(), k))
            annotation_plot.getAxis("left").setLabel(k)
            previous_annotation = None
            for i, elt in enumerate(self.annotation_set.annotations[k]):
                # Generate region item
                seg = AnnotationItem(elt)
                seg._previous_annotation_item = previous_annotation
                if previous_annotation is not None:
                    previous_annotation._next_annotation_item = seg
                annotation_plot.addItem(seg)

            if T_max < self.annotation_set.annotations[k][-1].end_time:
                T_max = self.annotation_set.annotations[k][-1].end_time

            self.vbox.addWidget(annotation_plot)

        # Define the last annotation as the reference one
        index = self.vbox.count() - 1
        self.reference_plot = self.vbox.itemAt(index).widget()
        self.reference_plot.setLimits(xMin=0, xMax=T_max, yMin=0, yMax=1)
        self.reference_plot.hideAxis("bottom")

        # Lock everything else to the reference
        for i in range(index):
            w = self.vbox.itemAt(i).widget()
            w.hideAxis("bottom")
            w.setXLink(self.reference_plot)
            w.setLimits(
                xMin=0,
                xMax=T_max,
                yMin=0,
                yMax=1,
            )


class AnnotationItem(SegmentItem):
    """Item to visualize an annotation.

    An annotation is a segment with a label

    Attributes
    ----------
    label : str
        The label of the annotation

    """

    def __init__(self, annotation, showLabel=True):
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

        # Some adaptations
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 0))
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
                player.play(start=self.start, end=self.end)
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

        controller.update_current_annotation(self)

        # Toggle the selected flag
        self._selected = not self._selected

        # Update the brush
        if self._selected:
            brush = QtGui.QBrush(QtGui.QColor(255, 0, 0, 50))
        else:
            brush = self._default_brush
        self.setBrush(brush)
        self.update()

    def updateLabel(self, label):
        self._segment.label = label
        self._text.setText(label)
        self._text.setPos((self._segment.start_time + self._segment.end_time) / 2, 0.5)
