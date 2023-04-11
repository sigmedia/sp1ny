#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Package containing modules which provides the key GUI components

LICENSE
"""

import sys

# Plotting & rendering
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

# GUI
from .one_shot import OneShotArea
from ..core.wav import PlayerControllerWidget
from ..core import plugin_entry_dict

from ..annotations.control import ControlLayout

import importlib
import pkgutil

import pyprag.plugins


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

        self._annotation_layout = ControlLayout(self)
        tab2 = QtWidgets.QWidget()
        tabs.addTab(tab2, "Annotations")
        tab2.setLayout(self._annotation_layout)

        tab2 = QtWidgets.QWidget()
        tabs.addTab(tab2, "Wav/Signal")

        right_layout.addWidget(tabs)

        ##########################################
        # Define the left part of the window
        ##########################################
        self._plot_area = OneShotArea(self._wav, frameshift, annotation)
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self._plot_area)

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
        options = QtGui.QFileDialog.Options()
        options |= QtGui.QFileDialog.DontUseNativeDialog
        # NOTE: how to concatente filters: "All Files (*);;Wav Files (*.wav)"
        filename, _ = QtGui.QFileDialog.getOpenFileName(
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
        self._plot_area.selectPlugin(controller)
        self.selectColorMap(self._cmap_list.currentText())

    def selectColorMap(self, cmap_name):
        self._plot_area.updateColorMap(cmap_name)


def define_palette(app):
    app.setStyle("Fusion")

    dark_palette = QtGui.QPalette()

    dark_palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
    dark_palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
    dark_palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
    dark_palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
    dark_palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    dark_palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)

    app.setPalette(dark_palette)

    app.setStyleSheet("QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }")


def build_gui(app, infos, frameshift, annotation=None):

    # Generate application
    define_palette(app)
    win = GUIVisu(infos, frameshift, annotation)
    win.setWindowTitle("PyPraG")

    # Start the application
    win.show()
    if (sys.flags.interactive != 1) or not hasattr(QtCore, "PYQT_VERSION"):
        app.exec()
