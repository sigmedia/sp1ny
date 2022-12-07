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

from pyqtgraph.Qt import QtGui

app = QtGui.QApplication(["PyPraG"])


# Annotation
try:
    from pyprag.annotations import HTKAnnotation, TGTAnnotation
    from pyprag.gui import build_gui
except Exception:
    pass

###############################################################################
# global constants
###############################################################################
LEVEL = [logging.WARNING, logging.INFO, logging.DEBUG]


###############################################################################
# Functions
###############################################################################
def entry_point(args, logger):
    """Main entry function"""

    if (args.annotation_file == "") and (args.wav_file == "") and (args.coefficient_file == ""):
        logger.error(
            "You need to give an annotation file (-a, --annotation-file), "
            + "a coefficient file (-c, --coefficient-file) and/or a wav file (-w, --wav-file)"
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
    else:
        logger.info("Loading coefficient file")
        if args.dimension is None:
            raise Exception("The coefficient file is given but not the dimension of the coefficient vector")

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
    infos = (wav, args.wav_file)
    build_gui(app, infos, frameshift, annotation)


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
    parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
    parser.add_argument("-c", "--coefficient-file", default="", type=str, help="The coefficient file")
    parser.add_argument(
        "-d",
        "--dimension",
        default=0,
        type=int,
        help="The dimension of the coefficient vector (negative shape is assumed to be (-1, d), positive (d, -1))",
    )
    parser.add_argument("-f", "--frameshift", default=5, type=float, help="The frameshift in milliseconds")
    parser.add_argument("-w", "--wav_file", default="", type=str, help="The wave file")

    # Parsing arguments
    args = parser.parse_args()

    # create logger and formatter
    logger = logging.getLogger()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Verbose level => logging level
    log_level = args.verbosity
    if args.verbosity >= len(LEVEL):
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
