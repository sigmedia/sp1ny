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
from ..wav.control import PlayerWidget


# Interpret image data as row-major instead of col-major
pg.setConfigOptions(imageAxisOrder="row-major")


class GUIVisu(QtGui.QMainWindow):
    def __init__(self, infos, frameshift, annotation):
        super().__init__()

        self._wav = infos[0]
        self._coef = infos[1]
        self._filename = infos[2]

        ##########################################
        # Setup the Menubar
        ##########################################
        menuBar = self.menuBar()
        file_menu = QtWidgets.QMenu("&File", self)

        # Add open shortcut
        self.openAction = QtWidgets.QAction("&Open wav...", self)
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
        player_widget = PlayerWidget(self._filename, self._wav)
        player_toolbar.addWidget(player_widget)

        ##########################################
        # Setup the status bar
        ##########################################
        self.statusbar = self.statusBar()
        self._filename_label = QtWidgets.QLabel(self._filename)
        self.statusbar.addPermanentWidget(self._filename_label)

        ##########################################
        # Define the left part of the window
        ##########################################
        self._plot_area = OneShotArea(self._wav, self._coef, frameshift, annotation)
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self._plot_area)

        ##########################################
        # Define the right part of the window
        ##########################################
        right_layout = QtWidgets.QVBoxLayout()

        # Initialize tab screen
        tabs = QtWidgets.QTabWidget()
        tab1 = QtWidgets.QWidget()
        tabs.addTab(tab1, "Data/Visualization")
        cur_layout = QtWidgets.QVBoxLayout(self)
        # eq_widget = EqWidget(self, self._wav)
        # cur_layout.addWidget(eq_widget)
        tab1.setLayout(cur_layout)

        tab2 = QtWidgets.QWidget()
        tabs.addTab(tab2, "Annotations")

        tab2 = QtWidgets.QWidget()
        tabs.addTab(tab2, "Wav/Signal")

        right_layout.addWidget(tabs)

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

    def openFile(self):
        options = QtGui.QFileDialog.Options()
        options |= QtGui.QFileDialog.DontUseNativeDialog
        # NOTE: how to concatente filters: "All Files (*);;Wav Files (*.wav)"
        filename, _ = QtGui.QFileDialog.getOpenFileName(
            self, "Loading wav file", "", "Wav Files (*.wav)", options=options
        )
        if filename:
            self._filename_label.setText(filename)


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
