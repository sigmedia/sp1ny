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

# Audio, dsp
import librosa
import pyworld as pw

# Plotting
import matplotlib.cm
from pyqtgraph.dockarea import *
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

# Utils
import re

# Annotation
from pyprag.annotation.htk_lab import *

# GUI
from pyprag.gui.utils import *
from pyprag.gui.comparison_area import *

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
    def __init__(self, ref_infos, other_infos, frameshift, annotation):
        super().__init__()

        self.plot_area = NSIMComparisonArea(ref_infos, other_infos, frameshift, annotation)

        ##########################################
        # Define the left part of the window
        ##########################################
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self.plot_area)

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



###############################################################################
# Functions
###############################################################################
def build_gui(ref_infos, other_infos, frameshift, annotation=None):

    # Generate application
    app = QtGui.QApplication(["ok"])
    win = GUIVisu(ref_infos, other_infos, frameshift, annotation)
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


def load_coef(f_coef, dim):
    coef = np.fromfile(f_coef, dtype=np.float32)
    coef = coef.reshape((len(coef)//dim, dim))
    return coef



###############################################################################
# Main function
###############################################################################
def main():
    """Main entry function
    """
    global args

    # Load annotation
    annotation = None
    if args.annotation_file is not None:
        annotation = HTKAnnotation(args.annotation_file)

    # Load Reference
    ref = load_coef(args.coef_ref_file, args.dim)
    ref_wav = librosa.core.load(args.wav_ref_file)

    # Load Other
    other = load_coef(args.coef_other_file, args.dim)
    other_wav = librosa.core.load(args.wav_other_file)

    # Adapt sizes
    m = np.min((ref.shape[0], other.shape[0]))
    ref = ref[0:m, :]
    other = other[0:m, :]
    assert ref.shape[0] == other.shape[0]

    # Generate info maps
    ref_infos = (ref, ref_wav, args.coef_ref_file)
    other_infos = (other, other_wav, args.coef_other_file)

    # # Define axes
    # y = np.logspace(np.log10(250), np.log10(16e3), args.dim)

    # # Cutoff
    # s = 0
    # e = args.dim
    # if args.end != np.Inf:
    #     assert (args.end < args.dim) and (args.start < args.end)
    #     e = args.end

    # if args.start > 0:
    #     assert (args.start < args.end)
    #     s = args.start

    # if (s > 0)  or (e <= args.dim):
    #     ref = ref[:, s:e]
    #     other = other[:, s:e]
    #     y = y[s:e]


    build_gui(ref_infos, other_infos, args.frameshift, annotation)


###############################################################################
#  Envelopping
###############################################################################
if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description="")

        # Add options
        parser.add_argument("-a", "--annotation_file", default=None, type=str,
                            help="The annotation file (HTK full label for now)")
        parser.add_argument("-d", "--dim", default=40, type=int,
                            help="The dimension of one frame")
        parser.add_argument("-f", "--frameshift", default=0.005, type=float,
                            help="The coefogram frameshift")
        parser.add_argument("-l", "--log_file", default=None,
                            help="Logger file")
        parser.add_argument("-s", "--start", default=0, type=int,
                            help="start position for the vector")
        parser.add_argument("-e", "--end", default=np.Inf, type=int,
                            help="end position for the vector")
        parser.add_argument("-v", "--verbosity", action="count", default=0,
                            help="increase output verbosity")

        # Add arguments
        parser.add_argument("wav_ref_file")
        parser.add_argument("coef_ref_file")
        parser.add_argument("wav_other_file")
        parser.add_argument("coef_other_file")

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
