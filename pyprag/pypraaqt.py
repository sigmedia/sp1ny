#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION


LICENSE
    This script is in the public domain, free from copyrights or restrictions.
    Created: 24 October 2019
"""

# System/default
import sys

# Arguments
import argparse

# Messaging/logging
import logging

# Linear algebra
import numpy as np

# Audio, dsp
import librosa

# Plotting & rendering
from pyqtgraph.dockarea import *
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

# Signal processing helpers
from pyprag.sig_proc.spectrum import *

# Annotation
from pyprag.annotation.htk_lab import *
from pyprag.annotation.textgrid import *

# GUI
from pyprag.gui.one_shot import *
from pyprag.components.wav.control import PlayerWidget
from pyprag.gui.control_panels.signal import EqWidget

###############################################################################
# global constants
###############################################################################
LEVEL = [logging.WARNING, logging.INFO, logging.DEBUG]

# Interpret image data as row-major instead of col-major
pg.setConfigOptions(imageAxisOrder="row-major")

###############################################################################
# Functions
###############################################################################
class GUIVisu(QtGui.QMainWindow):
    def __init__(self, infos, frameshift, annotation):
        super().__init__()

        self._wav = infos[0]
        self._coef = infos[1]
        self._filename = infos[2]
        self._plot_area = OneShotArea(self._wav, self._coef, frameshift, annotation)

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
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self._plot_area)

        ##########################################
        # Define the right part of the window
        ##########################################
        right_layout = QtWidgets.QVBoxLayout()

        # Initialize tab screen
        tabs = QtWidgets.QTabWidget()
        tab1 = QtWidgets.QWidget()
        tabs.addTab(tab1,"Signal")
        cur_layout = QtWidgets.QVBoxLayout(self)
        eq_widget = EqWidget(self, self._wav)
        cur_layout.addWidget(eq_widget)
        tab1.setLayout(cur_layout)

        tab2 = QtWidgets.QWidget()
        tabs.addTab(tab2,"Text")
        right_layout.addWidget(tabs)

        ##########################################
        # Finalize the main part layout
        ##########################################
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(left_layout, 10)
        main_layout.addLayout(right_layout, 2)

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
        filename, _ = QtGui.QFileDialog.getOpenFileName(self,"Loading wav file", "","Wav Files (*.wav)", options=options)
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

def build_gui(infos, frameshift, annotation=None):

    # Generate application
    app = QtGui.QApplication(["PyPraaQt"])
    define_palette(app)
    win = GUIVisu(infos, frameshift, annotation)
    win.setWindowTitle("PyPraaQt")

    # Start the application
    win.show()
    if (sys.flags.interactive != 1) or not hasattr(QtCore, "PYQT_VERSION"):
        app.exec()


def entry_point(args, logger):
    """Main entry function"""

    if (
        (args.annotation_file == "")
        and (args.wav_file == "")
        and (args.coefficient_file == "")
    ):
        logger.error(
            "You need to give an annotation file (-a, --annotation-file), a coefficient file (-c, --coefficient-file) and/or a wav file (-w, --wav-file)"
        )
        sys.exit(-1)

    # Load waves
    wav = None
    if args.wav_file != "":
        logger.info("Loading wav")
        wav = librosa.core.load(args.wav_file, sr=None)

    # Convert frameshift from ms to s
    frameshift = args.frameshift / 1000

    # Compute spectrum
    coef_matrix = None
    if args.coefficient_file == "":
        if wav is not None:
            logger.info("Compute spectrogram")
            sp_analyzer = SpectrumAnalysis(wav, frameshift=frameshift)
            coef_matrix = sp_analyzer._spectrum
    else:
        logger.info("Loading coefficient file")
        if args.dimension is None:
            raise Exception(
                "The coefficient file is given but not the dimension of the coefficient vector"
            )

        coef_matrix = np.fromfile(args.coefficient_file, dtype=np.float32)
        if args.dimension < 0:
            coef_matrix = coef_matrix.reshape((-1, -args.dimension))
        else:
            coef_matrix = coef_matrix.reshape((args.dimension, -1)).T

    # Load annotation
    logger.info("Load annotation")
    annotation = None
    if args.annotation_file != "":
        if args.annotation_file.endswith(".lab"):
            annotation = HTKAnnotation(args.annotation_file, wav)
        elif args.annotation_file.endswith(".TextGrid"):
            annotation = TGTAnnotation(args.annotation_file, wav)
        else:
            raise Exception("The annotation cannot be parsed, format is unknown")

    # Generate window
    logger.info("Rendering")
    infos = (wav, coef_matrix, args.wav_file)
    build_gui(infos, frameshift, annotation)


def main():
    parser = argparse.ArgumentParser(description="")

    # Add options
    parser.add_argument(
        "-a",
        "--annotation-file",
        default="",
        type=str,
        help="The annotation file (HTK label or TextGrid)",
    )
    parser.add_argument("-l", "--log-file", default="", help="Logger file")
    parser.add_argument(
        "-v", "--verbosity", action="count", default=0, help="increase output verbosity"
    )
    parser.add_argument(
        "-c", "--coefficient-file", default="", type=str, help="The coefficient file"
    )
    parser.add_argument(
        "-d",
        "--dimension",
        default=0,
        type=int,
        help="The dimension of the coefficient vector (if negative shape is assumed to be (-1, d), if positive (d, -1))",
    )
    parser.add_argument(
        "-f", "--frameshift", default=5, type=int, help="The frameshift in milliseconds"
    )
    parser.add_argument("-w", "--wav_file", default="", type=str, help="The wave file")

    # Parsing arguments
    args = parser.parse_args()

    # create logger and formatter
    logger = logging.getLogger()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Verbose level => logging level
    log_level = args.verbosity
    if args.verbosity >= len(LEVEL):
        log_level = len(LEVEL) - 1
        logger.setLevel(log_level)
        logging.warning(
            "verbosity level is too high, I'm gonna assume you're taking the highest (%d)"
            % log_level
        )
    else:
        logger.setLevel(LEVEL[log_level])

    # create console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # create file handler
    if args.log_file != "":
        fh = logging.FileHandler(args.log_file)
        logger.addHandler(fh)

    # Running main function <=> run application
    entry_point(args, logger)


###############################################################################
#  Envelopping
###############################################################################
if __name__ == "__main__":
    main()
