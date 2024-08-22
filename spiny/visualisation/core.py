import logging

# Plotting
import matplotlib as mpl
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from pyqtgraph.dockarea import Dock

# Spiny
from spiny.ui.utils import cmapToColormap
from spiny.ui.helpers.widgets import ExtendedComboBox
from .plugin_management import plugin_entry_dict


class DataDock(Dock):
    def __init__(self, size, wav_plot):
        Dock.__init__(self, name="Place Hold", size=size)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Override the label
        self.label.sigClicked.connect(self.mouseClicked)
        self._data_plot = None
        self._wav_plot = wav_plot

    def removeWidget(self, widget):
        """
        Add a new widget to the interior of this Dock.
        Each Dock uses a QGridLayout to arrange widgets within.
        """
        self.widgets.remove(widget)
        i = self.layout.count() - 1
        cur_widget = self.layout.itemAt(i).widget()
        if cur_widget is not None:
            cur_widget.setParent(None)
        self.currentRow = self.currentRow - 1

    def setWidget(self, widget, name):
        # Ensure widgets are removed
        if self._data_plot is not None:
            self.removeWidget(self._data_plot)

        # Now define new one
        self._data_plot = widget
        self._data_plot.hideAxis("bottom")
        self._data_plot.getAxis("left").setWidth(50)

        # Add plot
        # self.data_plot.disableAutoRange()
        self.addWidget(self._data_plot)

        # Update the name
        self.setTitle(name)

    def updateColorMap(self, cmap_name):
        self.logger.debug("Generate ticks for data plotting")
        cmap_cls = mpl.colormaps[cmap_name]
        pos, rgba_colors = zip(*cmapToColormap(cmap_cls))
        cmap = pg.ColorMap(pos, rgba_colors)
        lut = cmap.getLookupTable(0.0, 1.0, 10)
        ticks = list(enumerate(lut))
        self.ticks = [(ticks[i][0] / ticks[-1][0], ticks[i][1]) for i in range(len(ticks))]
        if self._data_plot is not None:
            self._data_plot.setTicks(self.ticks)

    def selectPlugin(self, controller):
        controller.extract()
        self.setWidget(controller._widget, controller._name)
        self._data_plot.setXLink(self._wav_plot)

    def mouseClicked(self):
        pass


class VisualisationController(QtWidgets.QWidget):
    def __init__(self, parent, visualisation_area):
        super().__init__(parent=parent)
        controller_layout = QtWidgets.QVBoxLayout(self)
        self._visualisation_area = visualisation_area

        # Populate the list of plugins
        self._plugin_list = ExtendedComboBox(self)
        self._plugin_list.addItem("None")
        for elt in plugin_entry_dict:
            self._plugin_list.addItem(elt)

        # NOTE: Raw DATA is a joker
        if "Raw DATA" in plugin_entry_dict:
            self._plugin_list.setCurrentText("Raw DATA")

        self._plugin_list.currentTextChanged.connect(self.selectPlugin)

        # Populate the list of plugins
        self._cmap_list = ExtendedComboBox(self)
        cmaps = [
            # Uniform
            "viridis",
            "plasma",
            "inferno",
            "magma",
            "cividis",
            # Sequential
            "binary",
            "gray",
            "bone",
            "hot",
            "copper",
        ]
        for elt in cmaps:
            self._cmap_list.addItem(elt)
        self._cmap_list.currentTextChanged.connect(self.selectColorMap)

        general_box_layout = QtWidgets.QGridLayout()
        general_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        l1 = QtWidgets.QLabel("Plugin")
        l2 = QtWidgets.QLabel("Colormap")
        general_box_layout.addWidget(l1, 0, 0)
        general_box_layout.addWidget(l2, 1, 0)
        general_box_layout.addWidget(self._plugin_list, 0, 1)
        general_box_layout.addWidget(self._cmap_list, 1, 1)

        general_box = QtWidgets.QGroupBox("General Data Visualization")
        general_box.setLayout(general_box_layout)
        controller_layout.addWidget(general_box)

        place_holder = QtWidgets.QVBoxLayout()
        controller_layout.addLayout(place_holder)
        self.setLayout(controller_layout)

        # Show the default plugin and the default colormap
        # NOTE: think about a configuration bit?
        self.selectPlugin(self._plugin_list.currentText())
        self.selectColorMap(self._cmap_list.currentText())

    def selectPlugin(self, current):
        if current.lower() == "none":
            self._visualisation_area.hide()
            return

        # NOTE: this is here because we lack a better way to avoid issues during completion
        if current not in plugin_entry_dict:
            return

        controller = plugin_entry_dict[current]
        i = self.layout().count() - 1
        cur_widget = self.layout().itemAt(i).widget()
        if cur_widget is not None:
            cur_widget.setParent(None)

        controller.setControlPanel(self.layout())
        self._visualisation_area.selectPlugin(controller)
        self.selectColorMap(self._cmap_list.currentText())
        self._visualisation_area.show()

    def selectColorMap(self, cmap_name):
        self._visualisation_area.updateColorMap(cmap_name)
