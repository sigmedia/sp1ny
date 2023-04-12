import sys

# Logging
import logging

# Linear algebra
import numpy as np

# Plotting
import matplotlib as mpl
from pyqtgraph.dockarea import DockArea
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

# GUI
import importlib
import pkgutil

# pyprag internal packages
from .gui.theme import define_palette
from .gui.utils import cmapToColormap
from .core.wav.visualisation import WavDock
from .annotations.visualisation import AnnotationDock
from .core import DataDock
from .core.wav import PlayerControllerWidget
from .core import plugin_entry_dict
from .annotations import controller as annotation_controller

import pyprag.plugins  # NOTE: we can't use relative import as the prefix is used to validate the plugins


#####################################################################################################
# Classes
#####################################################################################################


class VisualisationArea(DockArea):
    """DockArea filled with a plot containing a waveform and a give data (matrix only for now) as well
    as optional annotations.

    Attributes
    ----------
    wav : tuple(np.array, int)
        The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

    coef : np.array
       The matrix of coefficients to render

    annotation: pypgrag.annotation.AnnotationLoader
       The annotations if available, else None

    ticks : TODO
        The color map ticks
    """

    def __init__(self, wav, frameshift, annotation=None):
        """
        Parameters
        ----------
        wav : tuple(np.array, int)
            The signal information as loaded using librosa. The tuple contain an array of samples and the sample rate.

        coef : np.array
           The matrix of coefficients to render

        frameshift : float
           The frameshift used to extract the coefficients from the waveform

        annotation: pypgrag.annotation.AnnotationLoader, optional
           The annotation of object. (Default: None)

        color_map: matplotlib.cm.ColorMap, optional
           The color map used for the data rendering. (default: matplotlib.cm.bone)
        """
        # Superclass initialisation
        DockArea.__init__(self)

        self.logger = logging.getLogger("VisualisationArea")

        self.annotation = annotation
        if wav is not None:
            self.wav = wav
        else:
            self.wav = (np.zeros((self.coef.shape[0])), 1 / frameshift)
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
        self._dock_wav = WavDock("Signal", (950, 20), self.wav)

        # Generate data part
        self.logger.debug("Plot coefficient part")

        # controller = plugin_entry_list[0]
        # controller.setWav(self.wav[0], self.wav[1], dock_wav.wav_plot)
        # controller.extract()
        # controller._widget.setTicks(self.ticks)
        self._dock_coef = DataDock(
            (950, 200),
        )

        # Generate annotation part
        if self.annotation is not None:
            self.logger.debug("Plot annotation part")
            dock_align = AnnotationDock(
                "Annotations", (950, 20), self.annotation
            )  # Size doesn't seem to affect anything

        # Link X-Axis
        self.logger.debug("Link everything")
        self._dock_wav.wav_plot.setLabel("bottom", "Time", units="s")
        if self.annotation is not None:
            dock_align.reference_plot.setXLink(self._dock_wav.wav_plot)

        # - Add docks
        self.logger.debug("Add docks to the area")
        self.addDock(self._dock_wav, "left")
        if self.annotation is not None:
            self.addDock(dock_align, "top", self._dock_wav)
            self.addDock(self._dock_coef, "top", dock_align)
        else:
            self.addDock(self._dock_coef, "top", self._dock_wav)

    def selectPlugin(self, controller):
        controller.setWav(self.wav[0], self.wav[1], self._dock_wav.wav_plot)
        controller.extract()
        self._dock_coef.setWidget(controller._widget, controller._name)


# Discover plugins
def iter_namespace(ns_pkg):
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")


discovered_plugins = {name: importlib.import_module(name) for finder, name, ispkg in iter_namespace(pyprag.plugins)}

# Interpret image data as row-major instead of col-major
pg.setConfigOptions(imageAxisOrder="row-major")


class GUIVisu(QtWidgets.QMainWindow):
    def __init__(self, infos, frameshift, annotation):
        super().__init__()

        self._wav = infos[0]
        self._filename = infos[1]

        ##########################################
        # Setup the Menubar
        ##########################################
        menuBar = self.menuBar()
        file_menu = QtWidgets.QMenu("&File", self)

        # Add open shortcut
        self.openAction = QtGui.QAction("&Open wav...", self)
        self.openAction.triggered.connect(self.openFile)
        self.openAction.setShortcut("Ctrl+o")
        file_menu.addAction(self.openAction)

        # Add exit shortcut!
        self.exitAction = QtGui.QAction(("E&xit"), self)
        self.exitAction.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        self.addAction(self.exitAction)
        self.exitAction.triggered.connect(self.close)
        file_menu.addAction(self.exitAction)
        menuBar.addMenu(file_menu)

        ##########################################
        # Setup the toolbar
        ##########################################
        player_toolbar = self.addToolBar("Player")
        player_widget = PlayerControllerWidget(self._filename, self._wav)
        player_toolbar.addWidget(player_widget)

        ##########################################
        # Setup the status bar
        ##########################################
        self.statusbar = self.statusBar()
        self._filename_label = QtWidgets.QLabel(self._filename)
        self.statusbar.addPermanentWidget(self._filename_label)

        ##########################################
        # Define the right part of the window
        ##########################################
        right_layout = QtWidgets.QVBoxLayout()

        # Initialize tab screen
        tabs = QtWidgets.QTabWidget()
        tab1 = QtWidgets.QWidget()
        tabs.addTab(tab1, "Data/Visualization")
        self._control_layout = QtWidgets.QVBoxLayout(self)

        # Populate the list of plugins
        self._plugin_list = QtWidgets.QComboBox(self)
        for elt in plugin_entry_dict:
            self._plugin_list.addItem(elt)

        # NOTE: Raw DATA is a joker
        if "Raw DATA" in plugin_entry_dict:
            self._plugin_list.setCurrentText("Raw DATA")

        self._plugin_list.currentTextChanged.connect(self.selectPlugin)

        # Populate the list of plugins
        self._cmap_list = QtWidgets.QComboBox(self)
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
        self._control_layout.addWidget(general_box)

        place_holder = QtWidgets.QVBoxLayout()
        self._control_layout.addLayout(place_holder)
        tab1.setLayout(self._control_layout)

        self._annotation_layout = annotation_controller
        # self._annotation_layout.setParent(self)
        tab2 = QtWidgets.QWidget()
        tabs.addTab(tab2, "Annotations")
        tab2.setLayout(self._annotation_layout)

        tab2 = QtWidgets.QWidget()
        tabs.addTab(tab2, "Wav/Signal")

        right_layout.addWidget(tabs)

        ##########################################
        # Define the left part of the window
        ##########################################
        self._visualisation_area = VisualisationArea(self._wav, frameshift, annotation)
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self._visualisation_area)

        ##########################################
        # Finalize the main part layout
        ##########################################
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(left_layout, 9)
        main_layout.addLayout(right_layout, 3)

        ##########################################
        # Set the window layout
        ##########################################
        cent_widget = QtWidgets.QWidget()
        cent_widget.setLayout(main_layout)
        self.setCentralWidget(cent_widget)

        # Show the default plugin and the default colormap
        # NOTE: think about a configuration bit?
        self.selectPlugin(self._plugin_list.currentText())
        self.selectColorMap(self._cmap_list.currentText())

    def openFile(self):
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        # NOTE: how to concatente filters: "All Files (*);;Wav Files (*.wav)"
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Loading wav file", "", "Wav Files (*.wav)", options=options
        )
        if filename:
            self._filename_label.setText(filename)

    def selectPlugin(self, current):
        controller = plugin_entry_dict[current]
        i = self._control_layout.count() - 1
        cur_widget = self._control_layout.itemAt(i).widget()
        if cur_widget is not None:
            cur_widget.setParent(None)

        controller.setControlPanel(self._control_layout)
        self._visualisation_area.selectPlugin(controller)
        self.selectColorMap(self._cmap_list.currentText())

    def selectColorMap(self, cmap_name):
        self._visualisation_area.updateColorMap(cmap_name)


def build_gui(app, infos, frameshift, annotation=None):

    # Generate application
    define_palette(app)
    win = GUIVisu(infos, frameshift, annotation)
    win.setWindowTitle("PyPraG")

    # Start the application
    win.show()
    if (sys.flags.interactive != 1) or not hasattr(QtCore, "PYQT_VERSION"):
        app.exec()
