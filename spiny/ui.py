from __future__ import annotations

import types
from collections.abc import Iterator

import os
import sys

# Logging
import logging

# Plotting
from pyqtgraph.dockarea import DockArea
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

# GUI
import importlib
import pkgutil

# spiny internal packages
from .gui.theme import define_palette
from .gui.colormaps import COLORMAP_NAMES, colormap_ticks
from .gui.helpers.widgets import ExtendedComboBox
from .core.wav.visualisation import WavDock
from .core.wav import get_controller as get_audio_controller
from .annotations.visualisation import AnnotationDock
from .core import DataController, DataDock
from .core import player
from .core.wav import PlayerControllerWidget
from .core import plugin_entry_dict
from .annotations import get_controller as get_annotation_controller

import spiny.plugins  # NOTE: we can't use relative import as the prefix is used to validate the plugins

#####################################################################################################
# Classes
#####################################################################################################


class VisualisationArea(DockArea):
    """Area of the main window stacking the data plot, the annotation tiers and the waveform

    Every plot shares the time axis of the waveform plot.
    """

    def __init__(self) -> None:
        DockArea.__init__(self)

        # NOTE: the sizes are only initial proportions, the docks can be resized by the user
        self._dock_wav = WavDock("Signal", (950, 20))
        self._dock_wav.wav_plot.setLabel("bottom", "Time", units="s")
        self._dock_coef = DataDock((950, 200))
        self._dock_annotation = AnnotationDock("Annotations", (950, 20), self._dock_wav.wav_plot)

        self.addDock(self._dock_wav, "left")
        self.addDock(self._dock_annotation, "top", self._dock_wav)
        self.addDock(self._dock_coef, "top", self._dock_annotation)

    def updateColorMap(self, cmap_name: str) -> None:
        """Apply a colormap to the data plot

        Parameters
        ----------
        cmap_name : str
            The colormap name (one of spiny.gui.colormaps.COLORMAP_NAMES)
        """
        if self._dock_coef._data_plot is not None:
            self._dock_coef._data_plot.setTicks(colormap_ticks(cmap_name))

    def selectPlugin(self, controller: DataController) -> None:
        """Extract the data of a plugin and show its widget in the data dock

        Parameters
        ----------
        controller : spiny.core.DataController
            The plugin controller
        """
        controller.setWavPlot(self._dock_wav.wav_plot)
        controller.extract()
        self._dock_coef.setWidget(controller.widget, controller.name)


# Discover plugins
def iter_namespace(ns_pkg: types.ModuleType) -> Iterator[pkgutil.ModuleInfo]:
    """List the modules of a namespace package

    Parameters
    ----------
    ns_pkg : module
        The package

    Returns
    -------
    iterator(pkgutil.ModuleInfo)
        The modules, with absolute names (so that they can be imported directly)
    """
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")


def discover_plugins() -> dict[str, types.ModuleType]:
    """Import every plugin package of spiny.plugins

    A plugin which fails to import (missing optional dependency, incompatible version, bug, ...) is
    reported and skipped: it must never prevent the application from starting.
    """
    logger = logging.getLogger(__name__)
    plugins = dict()
    for _, name, _ in iter_namespace(spiny.plugins):
        try:
            plugins[name] = importlib.import_module(name)
        except Exception as ex:
            logger.warning('The plugin "%s" is not available: %s', name, ex)
            logger.debug("Plugin import failure", exc_info=True)
    return plugins


class GUIVisu(QtWidgets.QMainWindow):
    """Main window: player toolbar, plots (data, annotations, waveform) on the left, control tabs on the right"""

    def __init__(self) -> None:
        super().__init__()
        self._createMenuBar()
        self.addToolBar("Player").addWidget(PlayerControllerWidget())
        self._filename_label = QtWidgets.QLabel(str(player.filename or ""))
        self.statusBar().addPermanentWidget(self._filename_label)

        self._visualisation_area = VisualisationArea()
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._createDataTab(), "Data/Visualization")
        tabs.addTab(self._createAnnotationTab(), "Annotations")
        tabs.addTab(self._createAudioTab(), "Audio")

        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addWidget(self._visualisation_area, 9)
        main_layout.addWidget(tabs, 3)
        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Show the default plugin with the default colormap
        self.selectPlugin(self._plugin_list.currentText())
        self.selectColorMap(self._cmap_list.currentText())

    def _createMenuBar(self) -> None:
        """Create the File menu (open an audio file, quit)"""
        file_menu = self.menuBar().addMenu("&File")

        open_action = QtGui.QAction("&Open wav...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.openFile)
        file_menu.addAction(open_action)

        exit_action = QtGui.QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _createDataTab(self) -> QtWidgets.QWidget:
        """Create the tab choosing the data plugin and the colormap; the plugin panel is added below them

        Returns
        -------
        QtWidgets.QWidget
            The tab
        """
        self._plugin_list = ExtendedComboBox(self)
        self._plugin_list.addItems(list(plugin_entry_dict))
        if "Raw DATA" in plugin_entry_dict:  # coefficients given on the command line are shown first
            self._plugin_list.setCurrentText("Raw DATA")
        self._current_controller: DataController | None = None
        self._plugin_list.currentTextChanged.connect(self.selectPlugin)

        self._cmap_list = ExtendedComboBox(self)
        self._cmap_list.addItems(list(COLORMAP_NAMES))
        self._cmap_list.currentTextChanged.connect(self.selectColorMap)

        general_box_layout = QtWidgets.QGridLayout()
        general_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        general_box_layout.addWidget(QtWidgets.QLabel("Plugin"), 0, 0)
        general_box_layout.addWidget(self._plugin_list, 0, 1)
        general_box_layout.addWidget(QtWidgets.QLabel("Colormap"), 1, 0)
        general_box_layout.addWidget(self._cmap_list, 1, 1)
        general_box = QtWidgets.QGroupBox("General Data Visualization")
        general_box.setLayout(general_box_layout)

        # NOTE: selectPlugin replaces the last item of this layout by the panel of the plugin: the empty
        #       layout added here is that place holder until a plugin is selected
        self._control_layout = QtWidgets.QVBoxLayout()
        self._control_layout.addWidget(general_box)
        self._control_layout.addLayout(QtWidgets.QVBoxLayout())

        tab = QtWidgets.QWidget()
        tab.setLayout(self._control_layout)
        return tab

    def _createAnnotationTab(self) -> QtWidgets.QWidget:
        """Create the annotation tab, connected to the annotation dock

        Returns
        -------
        QtWidgets.QWidget
            The tab
        """
        self._annotation_layout = get_annotation_controller()
        self._annotation_layout.setView(self._visualisation_area._dock_annotation)
        self._annotation_layout.resetView()
        tab = QtWidgets.QWidget()
        tab.setLayout(self._annotation_layout)
        return tab

    def _createAudioTab(self) -> QtWidgets.QWidget:
        """Create the audio tab (current file, equalizer)

        Returns
        -------
        QtWidgets.QWidget
            The tab
        """
        self._audio_layout = get_audio_controller()
        self._audio_layout.setLoadHandler(self.openFile)
        self._audio_layout.setCurrentFile(str(player.filename or ""))
        tab = QtWidgets.QWidget()
        tab.setLayout(self._audio_layout)
        return tab

    def openFile(self) -> None:
        """Ask for an audio file and load it (see `loadWav`)"""
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        # NOTE: how to concatente filters: "All Files (*);;Wav Files (*.wav)"
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Loading wav file", "", "Wav Files (*.wav);;All Files (*)", options=options
        )
        if filename:
            self.loadWav(filename)

    def loadWav(self, filename: str) -> None:
        """Load a new signal and refresh every view depending on it"""
        try:
            player.loadNewWav(filename)
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self, "Loading wav file", f'Cannot load "{filename}":\n{ex}')
            return

        self._filename_label.setText(filename)
        self._audio_layout.setCurrentFile(filename)
        self._visualisation_area._dock_wav.wav_plot.refresh()
        self._annotation_layout.resetView()
        self.selectPlugin(self._plugin_list.currentText())  # Re-extract the data from the new signal

    def selectPlugin(self, current: str) -> None:
        """Show the plugin of the given name (its control panel and its data)

        The data of the previously shown plugin is released.

        Parameters
        ----------
        current : str
            The plugin name (ignored if it is not a registered plugin, e.g. while typing in the combo box)
        """
        # NOTE: this is here because we lack a better way to avoid issues during completion
        if current not in plugin_entry_dict:
            return

        controller = plugin_entry_dict[current]

        # The previous plugin is not displayed anymore: free its data (it is re-extracted when selected again)
        if (self._current_controller is not None) and (self._current_controller is not controller):
            self._current_controller.release()
        self._current_controller = controller

        i = self._control_layout.count() - 1
        cur_widget = self._control_layout.itemAt(i).widget()
        if cur_widget is not None:
            # NOTE: deferred deletion, destroying the panel synchronously (setParent(None)) can crash
            self._control_layout.removeWidget(cur_widget)
            cur_widget.hide()
            cur_widget.deleteLater()

        controller.setControlPanel(self._control_layout)
        self._visualisation_area.selectPlugin(controller)
        self.selectColorMap(self._cmap_list.currentText())

    def selectColorMap(self, cmap_name: str) -> None:
        """Apply a colormap to the data plot

        Parameters
        ----------
        cmap_name : str
            The colormap name (one of spiny.gui.colormaps.COLORMAP_NAMES)
        """
        self._visualisation_area.updateColorMap(cmap_name)


def install_exception_hook(parent: QtWidgets.QWidget | None = None) -> None:
    """Report the exceptions raised in Qt slots in a dialog (and in the log) instead of only on stderr"""
    logger = logging.getLogger("spiny")

    def hook(
        exc_type: type[BaseException], exc_value: BaseException, exc_traceback: types.TracebackType | None
    ) -> None:
        """Log an unhandled exception and show it in a dialog

        Parameters
        ----------
        exc_type : type
            The exception class
        exc_value : BaseException
            The exception
        exc_traceback : traceback
            The traceback
        """
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
        QtWidgets.QMessageBox.critical(
            parent, "Unexpected error", f"{exc_type.__name__}: {exc_value}\n\nSee the log for the details."
        )

    sys.excepthook = hook


def build_gui(app: QtWidgets.QApplication, dark_activated: bool = False) -> None:
    """Create the main window and run the application (blocks until the window is closed)

    Parameters
    ----------
    app : QtWidgets.QApplication
        The application
    dark_activated : bool, optional
        Use the dark theme. (default: False)
    """
    # Generate application
    define_palette(app, dark_activated)
    app.aboutToQuit.connect(player.stop)

    # Plugins create widgets, so they are discovered only now that the application exists
    discover_plugins()
    win = GUIVisu()
    win.setWindowTitle("SpINY")
    install_exception_hook(win)

    # Start the application
    win.show()

    # NOTE: automated checks of the packaged application set SPINY_AUTOQUIT_MS to quit once the GUI is up
    autoquit = os.environ.get("SPINY_AUTOQUIT_MS")
    if autoquit:
        QtCore.QTimer.singleShot(int(autoquit), app.quit)

    if (sys.flags.interactive != 1) or not hasattr(QtCore, "PYQT_VERSION"):
        app.exec()
