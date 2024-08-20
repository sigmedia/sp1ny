# Logging
import logging

# Plotting
import matplotlib as mpl
from pyqtgraph.dockarea import DockArea
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

# Spiny
from spiny.ui.utils import cmapToColormap
from spiny.ui.helpers.widgets import ExtendedComboBox
from spiny.audio.visualisation import WavDock
from spiny.annotations.visualisation import AnnotationDock
from .base import DataDock

from .plugin_management import plugin_entry_dict

class VisualisationArea(DockArea):
    """DockArea filled with a plot containing a waveform and a give data (matrix only for now) as well
    as optional annotations.

    Attributes
    ----------

    ticks : TODO
        The color map ticks
    """

    def __init__(self, frameshift):
        """
        Parameters
        ----------
        frameshift : float
           The frameshift used to extract the coefficients from the waveform
        """
        # Superclass initialisation
        super().__init__()

        self.logger = logging.getLogger("VisualisationArea")
        self.frameshift = frameshift

        # - Generate color map
        self.__fill()

    def updateColorMap(self, cmap_name):
        self.logger.debug("Generate ticks for data plotting")
        cmap_cls = mpl.colormaps[cmap_name]
        pos, rgba_colors = zip(*cmapToColormap(cmap_cls))
        cmap = pg.ColorMap(pos, rgba_colors)
        lut = cmap.getLookupTable(0.0, 1.0, 10)
        ticks = list(enumerate(lut))
        self.ticks = [(ticks[i][0] / ticks[-1][0], ticks[i][1]) for i in range(len(ticks))]
        if self._dock_coef._data_plot is not None:
            self._dock_coef._data_plot.setTicks(self.ticks)

    def __fill(self):
        """Helper to fill the dock area"""
        # Generate wav part
        self.logger.debug("Plot waveform part")
        self._dock_wav = WavDock("Signal", (950, 20))

        # Generate data part
        self.logger.debug("Plot coefficient part")
        self._dock_coef = DataDock(
            (950, 200),
        )

        # Generate annotation part
        self.logger.debug("Plot annotation part")
        self._dock_annotation = AnnotationDock(
            "Annotations", (950, 20), self._dock_wav.wav_plot
        )  # Size doesn't seem to affect anything

        # Define the label on wav plots
        self._dock_wav.wav_plot.setLabel("bottom", "Time", units="s")

        # - Add docks
        self.logger.debug("Add docks to the area")
        self.addDock(self._dock_wav, "left")
        self.addDock(self._dock_annotation, "top", self._dock_wav)
        self.addDock(self._dock_coef, "top", self._dock_annotation)

    def selectPlugin(self, controller):
        controller.setWavPlot(self._dock_wav.wav_plot)
        controller.extract()
        self._dock_coef.setWidget(controller._widget, controller._name)

class VisualisationController(QtWidgets.QWidget):
    def __init__(self, parent, visualisation_area):
        super().__init__(parent=parent)
        controller_layout = QtWidgets.QVBoxLayout(self)
        self._visualisation_area = visualisation_area

        # Populate the list of plugins
        self._plugin_list = ExtendedComboBox(self)
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

    def selectColorMap(self, cmap_name):
        self._visualisation_area.updateColorMap(cmap_name)
