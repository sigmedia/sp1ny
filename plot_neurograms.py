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

# Plotting
import matplotlib.cm
from pyqtgraph.dockarea import *
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

# Utils
import re

# ???
from plot_area import PlotArea

###############################################################################
# global constants
###############################################################################
LEVEL = [logging.WARNING, logging.INFO, logging.DEBUG]

# Interpret image data as row-major instead of col-major
pg.setConfigOptions(imageAxisOrder='row-major')

###############################################################################
# global constants
###############################################################################
class NSIM:
    def __init__(self, r, d):
        self._window =  np.array([[0.0113, 0.0838, 0.0113],
                                  [0.0838, 0.6193, 0.0838],
                                  [0.0113, 0.0838, 0.0113]])
        self._window = self._window / np.sum(self._window)
        self._r = r
        self._d = d

    def compute(self):
        """NSIM Metric based on visqol implementation

        """
        # 2-D Gaussian filter of size 3 with std=0.5
        window_rotated = np.rot90(self._window, 2)

        # Prepare smoothing coefficient
        L = 160 # FIXME: hardcoded
        C1 = np.power(0.01 * L, 2)
        C2 = np.power(0.03 * L, 2) / 2

        # Mean part
        m_r = signal.convolve2d(self._r, window_rotated, 'valid') # Filter2 in matlab
        m_d = signal.convolve2d(self._d, window_rotated, 'valid') # Filter2 in matlab
        m_r_sq = m_r * m_r
        m_d_sq = m_d * m_d
        m_r_m_d = m_r * m_d

        # Std part
        s_r_sq = signal.convolve2d(self._r*self._r, window_rotated, 'valid') - m_r_sq # Filter2 in matlab
        s_d_sq = signal.convolve2d(self._d*self._d, window_rotated, 'valid') - m_d_sq # Filter2 in matlab
        s_r_d = signal.convolve2d(self._r*self._d, window_rotated, 'valid') - m_r_m_d # Filter2 in matlab
        s_r = np.sign(s_r_sq) * np.sqrt(np.abs(s_r_sq))
        s_d = np.sign(s_d_sq) * np.sqrt(np.abs(s_d_sq))

        # Compute subparts
        L_r_d = (2 * m_r * m_d + C1) / (m_r_sq + m_d_sq + C1) # Luminance
        S_r_d = (s_r_d + C2) / (s_r * s_d + C2) # Structural

        # Compute nsim
        nmap = L_r_d * S_r_d
        nsim = np.mean(nmap)

        return (nsim, nmap)


###############################################################################
# Functions
###############################################################################


def load_neurograms(f_neur, dim):
    neur = np.fromfile(f_neur, dtype=np.float32)
    neur = neur.reshape((len(neur)//dim, dim))
    return neur

# def compute_dist(ref, other):
#     ref[ref<=0.2] = 0
#     other[ref<=0.2] = 0
#     diff = np.abs(ref-other)
#     return diff

def compute_dist(ref, other):
    nsim = NSIM(ref, other)
    return nsim.compute()


def build_frame(ref_infos, other_infos, dist, frameshift, win, alignment=None):
    win.setWindowTitle('pyqtgraph example: PlotWidget')
    win.resize(1000, 620)
    area = PlotArea(ref_infos, other_infos, dist, frameshift, alignment)
    win.setCentralWidget(area)

def extract_alignment(alignment_file):
    alignment = []
    if alignment_file is not None:
        with open(alignment_file) as f:
            for l in f:
                # Preprocess
                l = l.strip()
                elts = l.split()
                assert len(elts) == 3

                # Convert to seconds
                elts[0] = int(elts[0]) / 10000000
                elts[1] = int(elts[1]) / 10000000

                # Extract monophone label
                m = re.search('-(.+?)\+', elts[2])
                if m:
                    elts[2] = m.group(1)
                else:
                    raise("label not correct : " + elts[2])

                # Finalize by adding everything to the list
                alignment.append(elts)
    return alignment

###############################################################################
# Main function
###############################################################################
def main():
    """Main entry function
    """
    global args

    f_ref = args.neur_ref_file
    f_other = args.neur_other_file

    # Load Neur
    ref = load_neurograms(f_ref, args.dim)
    other = load_neurograms(f_other, args.dim)
    m = np.min((ref.shape[0], other.shape[0]))
    ref = ref[0:m, :]
    other = other[0:m, :]
    assert ref.shape[0] == other.shape[0]

    # Define axes
    y = np.logspace(np.log10(250), np.log10(16e3), args.dim)

    # Cutoff
    s = 0
    e = args.dim
    if args.end != np.Inf:
        assert (args.end < args.dim) and (args.start < args.end)
        e = args.end

    if args.start > 0:
        assert (args.start < args.end)
        s = args.start

    if (s > 0)  or (e <= args.dim):
        ref = ref[:, s:e]
        other = other[:, s:e]
        y = y[s:e]

    # # Average!
    # m = np.max([np.max(ref), np.max(other)])
    # other = other / m
    # ref = ref / m

    # Smooth
    window =  np.array([[0.0113, 0.0838, 0.0113],
                        [0.0838, 0.6193, 0.0838],
                        [0.0113, 0.0838, 0.0113]])
    window = window / np.sum(window)
    ref = sp.ndimage.filters.convolve(ref, window, mode='constant')
    other = sp.ndimage.filters.convolve(other, window, mode='constant')

    # Some diff
    [nsim, nmap] = compute_dist(ref, other)
    print(nsim)

    # Compute proportion
    prop = np.count_nonzero(nmap >= 0.99) * 100.0 / (nmap.shape[0] * nmap.shape[1])
    print("prop = %03.2f %%" % prop)

    # Filter out values
    nmap_ma = np.ma.masked_where(nmap>=0.99, nmap)
    print(np.mean(nmap_ma))

    # Load waves
    ref_wav = librosa.core.load(args.wav_ref_file)
    other_wav = librosa.core.load(args.wav_other_file)

    # Load alignment
    alignment = extract_alignment(args.alignment_file)

    # Generate frame
    app = QtGui.QApplication([args.neur_ref_file])
    win = QtGui.QMainWindow()
    build_frame((ref, ref_wav, args.neur_ref_file),
                (other, other_wav, args.neur_other_file),
                nmap, args.frame_shift, win, alignment)

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
#  Envelopping
###############################################################################
if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description="")

        # Add options
        parser.add_argument("-a", "--alignment_file", default=None, type=str,
                            help="The alignment file (HTK full label for now)")
        parser.add_argument("-d", "--dim", default=40, type=int,
                            help="The dimension of one frame")
        parser.add_argument("-f", "--frame_shift", default=0.0064, type=float, # 0.0064 = mr, 0.00016 = ft
                            help="The neurogram frameshift")
        parser.add_argument("-l", "--log_file", default=None,
                            help="Logger file")
        parser.add_argument("-s", "--start", default=0, type=int,
                            help="start position for the vector")
        parser.add_argument("-e", "--end", default=np.Inf, type=int,
                            help="end position for the vector")
        parser.add_argument("-v", "--verbosity", action="count", default=0,
                            help="increase output verbosity")

        # Add arguments
        parser.add_argument("neur_ref_file")
        parser.add_argument("neur_other_file")
        parser.add_argument("wav_ref_file")
        parser.add_argument("wav_other_file")

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
