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
import os

# Arguments
import argparse

# Messaging/logging
import traceback
import time
import logging

# Profiling
import cProfile

# Linear algebra
import numpy as np
import scipy as sp
from scipy import signal
from fastdtw import fastdtw

# Audio, dsp
import librosa

# Plotting & rendering
import matplotlib.cm
from pyqtgraph.dockarea import *
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

# Utils
import re

# Player
from pyprag.audio.player import player

# Signal processing helpers
from pyprag.sig_proc.spectrum import *

# Annotation
from pyprag.annotation.htk_lab import *
from pyprag.annotation.textgrid import *

# GUI
from pyprag.gui.utils import *
from pyprag.gui.docks import *
from pyprag.gui.one_shot import *

###############################################################################
# global constants
###############################################################################
LEVEL = [logging.WARNING, logging.INFO, logging.DEBUG]

# Interpret image data as row-major instead of col-major
pg.setConfigOptions(imageAxisOrder='row-major')

###############################################################################
# Functions
###############################################################################
class GUIVisu(QtGui.QMainWindow):
    def __init__(self, infos, frameshift, annotation):
        super().__init__()

        self.wav = infos[0]
        self.coef = infos[1]
        self.filename = infos[2]
        self.plot_area = OneShotArea(self.wav, self.coef, frameshift, annotation)


        ##########################################
        # Setup the status bar
        ##########################################
        self.status = QtWidgets.QStatusBar()
        self.status.setMaximumHeight(20)
        self.status.showMessage(self.filename)

        ##########################################
        # Define the left part of the window
        ##########################################
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self.plot_area)
        left_layout.addWidget(self.status)

        ##########################################
        # Define the right part of the window
        ##########################################
        # Define play button
        self.bPlay = QtWidgets.QPushButton("Play", self)
        self.bPlay.clicked.connect(self.play)
        self.bPlay.setDefault(False)
        self.bPlay.setAutoDefault(False)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self.bPlay)

        ##########################################
        # Finalize the main part layout
        ##########################################
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(left_layout, 10)
        main_layout.addLayout(right_layout, 1)

        ##########################################
        # Set the window layout
        ##########################################
        cent_widget = QtWidgets.QWidget()
        cent_widget.setLayout(main_layout)
        self.setCentralWidget(cent_widget)


    def play(self):
        # Play subpart
        player.play(self.wav[0], self.wav[1])

def build_gui(infos, frameshift, annotation=None):

    # Generate application
    app = QtGui.QApplication(["ok"])
    win = GUIVisu(infos, frameshift, annotation)
    win.setWindowTitle('pyqtgraph example: PlotWidget')

    # Add exit shortcut!
    win.actionExit = QtGui.QAction(('E&xit'), win)
    win.actionExit.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
    win.addAction(win.actionExit)
    win.actionExit.triggered.connect(win.close)

    # Start the application
    win.show()
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()


def entry_point(args, logger):
    """Main entry function
    """

    # Load waves
    logger.info("Loading wav")
    wav = librosa.core.load(args.wav_file, sr=None)

    # Convert frameshift from ms to s
    frameshift = args.frameshift/1000

    # Compute spectrum
    if args.coefficient_file is None:
        logger.info("Compute spectrogram")
        sp_analyzer = SpectrumAnalysis(wav, frameshift=frameshift)
        coef_matrix = sp_analyzer.spectrum
    else:
        logger.info("Loading coefficient file")
        if args.dimension is None:
            raise Exception("The coefficient file is given but not the dimension of the coefficient vector")

        coef_matrix = np.fromfile(args.coefficient_file, dtype=np.float32)
        coef_matrix = coef_matrix.reshape((args.dimension, -1)).T

    # Load annotation
    logger.info("Load annotation")
    annotation = None
    if args.annotation_file is not None:
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
    parser.add_argument("-a", "--annotation_file", default=None, type=str,
                        help="The annotation file (HTK label or TextGrid)")
    parser.add_argument("-l", "--log_file", default=None,
                        help="Logger file")
    parser.add_argument("-v", "--verbosity", action="count", default=0,
                        help="increase output verbosity")
    parser.add_argument("-c", "--coefficient_file", default=None, type=str)
    parser.add_argument("-d", "--dimension", default=None, type=int)
    parser.add_argument("-f", "--frameshift", default=5, type=int)

    # Add arguments
    parser.add_argument("wav_file")

    # Parsing arguments
    args = parser.parse_args()

    # create logger and formatter
    logger = logging.getLogger()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Verbose level => logging level
    log_level = args.verbosity
    if (args.verbosity >= len(LEVEL)):
        log_level = len(LEVEL) - 1
        logger.setLevel(log_level)
        logging.warning("verbosity level is too high, I'm gonna assume you're taking the highest (%d)" % log_level)
    else:
        logger.setLevel(LEVEL[log_level])

    # create console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # create file handler
    if args.log_file is not None:
        fh = logging.FileHandler(args.log_file)
        logger.addHandler(fh)

    # Running main function <=> run application
    entry_point(args, logger)


###############################################################################
#  Envelopping
###############################################################################
if __name__ == '__main__':
    main()
