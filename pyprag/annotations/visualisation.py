import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from pyqtgraph.dockarea import Dock

from pyprag.gui.items import SegmentItem
from pyprag.core import player


class AnnotationDock(Dock):
    """Dock containing annotation informations

    Attributes
    ----------
    annotation: pyprag.annotation.AnnotationLoader
        The annotation loader object

    reference_plot : pg.PlotWidget
        The reference annotation tier rendering as we have a plot per tier

    """

    def __init__(self, name, size, annotation):
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
        self.annotation = annotation

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
        lim_factor = 1.1
        wav_data = player._data
        sr = player._sampling_rate
        T_max = wav_data.shape[0] / sr
        for k in self.annotation.segments:
            annotation_plot = pg.PlotWidget(name="%s_%s" % (self.name(), k))
            annotation_plot.disableAutoRange()
            annotation_plot.getAxis("left").setLabel(k)
            annotation_plot.setYRange(0, 1)
            for i, elt in enumerate(self.annotation.segments[k]):
                # Generate region item
                seg = AnnotationItem(elt)
                annotation_plot.addItem(seg)

            if T_max < self.annotation.segments[k][-1][1]:
                T_max = self.annotation.segments[k][-1][1]

            self.vbox.addWidget(annotation_plot)

        # Define the last annotation as the reference one
        index = self.vbox.count() - 1
        self.reference_plot = self.vbox.itemAt(index).widget()
        self.reference_plot.setLimits(xMax=T_max * lim_factor)
        self.reference_plot.hideAxis("bottom")

        # Lock everything else to the reference
        for i in range(index):
            w = self.vbox.itemAt(i).widget()
            w.hideAxis("bottom")
            w.setXLink(self.reference_plot)
            w.setLimits(xMax=T_max * lim_factor)


class AnnotationItem(SegmentItem):
    """Item to visualize an annotation.

    An annotation is a segment with a label

    Attributes
    ----------
    label : str
        The label of the annotation

    """

    def __init__(self, seg_infos, showLabel=True):
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
        super().__init__(seg_infos[0], seg_infos[1], movable=False)

        self.label = seg_infos[2]
        self._selected = False

        # Some adaptations
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 0))
        self.setBrush(brush)
        hover_brush = QtGui.QBrush(QtGui.QColor(0, 0, 255, 100))
        self.setHoverBrush(hover_brush)

        # Add label
        if showLabel:
            self._text = pg.TextItem(
                text=self.label,
                anchor=(0.5, 0.5),
                color=QtWidgets.QApplication.instance().palette().color(QtGui.QPalette.Text),
            )
            self._text.setPos((self.end + self.start) / 2, 0.5)
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
        self._text.setPos((self.end + self.start) / 2, 0.5)

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

        # # Check which key is pressed
        # modifier_pressed = ev.modifiers()

        if (ev.buttons() == QtCore.Qt.LeftButton) and (not ev.double()):
            print("wait what?")
            self.select()

    def select(self):
        self._selected = not self._selected

        # Indicate that the segment is selected by changing the background brush
        if self._selected:
            brush = QtGui.QBrush(QtGui.QColor(255, 0, 0, 50))
        else:
            brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 50))
        self.setBrush(brush)
