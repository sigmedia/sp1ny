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

# Linear algebra
import numpy as np
import scipy as sp
from scipy import signal
from fastdtw import fastdtw

# Audio, dsp
import librosa
import pyworld as pw

# Plotting & rendering
import matplotlib.cm
from pyqtgraph.dockarea import *
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

# Utils
import re

# Signal processing helpers
from sig_proc.spectrum import *

# Alignment
from alignment.htk_lab import *

# GUI
from gui.utils import *
from gui.docks import *
from gui.one_shot import *

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
    def __init__(self, wav, coef, frameshift, alignment):
        super().__init__()

        self.plot_area = OneShotArea(wav, coef, frameshift, alignment)
        self.plot_area.setMinimumSize(1000, 620)

        ##########################################
        # Setup the status bar
        ##########################################
        self.status = QtWidgets.QStatusBar()
        self.status.setMaximumSize(1000, 50)
        self.status.showMessage("Ok go maybe?!")

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
        # self.bPlay.clicked.connect(self.play)
        self.bPlay.setDefault(False)
        self.bPlay.setAutoDefault(False)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self.bPlay)

        ##########################################
        # Finalize the main part layout
        ##########################################
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(left_layout, 3)
        main_layout.addLayout(right_layout, 1)

        ##########################################
        # Set the window layout
        ##########################################
        cent_widget = QtWidgets.QWidget()
        cent_widget.setLayout(main_layout)
        self.setCentralWidget(cent_widget)


def build_gui(wav, coef, frameshift, alignment=None):

    # Generate application
    app = QtGui.QApplication(["ok"])
    win = GUIVisu(wav, coef, frameshift, alignment)
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


###############################################################################
# Main function
###############################################################################
def main():
    """Main entry function
    """
    global args

    # Load waves
    wav = librosa.core.load(args.wav_file, mono=True, sr=16000)

    # Compute spectrum
    frameshift=0.0005
    sp_analyzer = SpectrumAnalysis(wav, frameshift=frameshift)
    sp_analyzer.analyze()

    # Load alignment
    alignment = HTKAlignment(args.alignment_file, wav)

    # Generate window
    build_gui(wav, sp_analyzer.spectrum, frameshift, alignment)

###############################################################################
#  Envelopping
###############################################################################
if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description="")

        # Add options
        parser.add_argument("-a", "--alignment_file", default=None, type=str,
                            help="The alignment file (HTK full label for now)")
        parser.add_argument("-l", "--log_file", default=None,
                            help="Logger file")
        parser.add_argument("-v", "--verbosity", action="count", default=0,
                            help="increase output verbosity")

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

        # Debug time
        start_time = time.time()
        logger.info("start time = " + time.asctime())

        # Running main function <=> run application
        main()

        # Debug time
        logging.info("end time = " + time.asctime())
        logging.info('TOTAL TIME IN MINUTES: %02.2f' %
                     ((time.time() - start_time) / 60.0))

        # Exit program
        sys.exit(0)
    except KeyboardInterrupt as e:  # Ctrl-C
        raise e
    except SystemExit:  # sys.exit()
        pass
    except Exception as e:
        logging.error('ERROR, UNEXPECTED EXCEPTION')
        logging.error(str(e))
        traceback.print_exc(file=sys.stderr)
        sys.exit(-1)
