#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

LICENSE
    This script is in the public domain, free from copyrights or restrictions.
    Created: 17 January 2023
"""

# System/default
import sys

# Arguments
import argparse

# Messaging/logging
import logging
from logging.config import dictConfig

# Audio, dsp
import librosa

# PyQtGraph & create application
from pyqtgraph.Qt import QtWidgets

# PyPrag dedicated imports
from pyprag.core.data import controller

try:
    from pyprag.annotations import HTKAnnotation, TGTAnnotation
    from pyprag.gui import build_gui
except Exception as ex:
    raise ex


###############################################################################
# global constants
###############################################################################
LEVEL = [logging.WARNING, logging.INFO, logging.DEBUG]
APP = QtWidgets.QApplication(["PyPraG"])


###############################################################################
# Functions
###############################################################################
def configure_logger(args) -> logging.Logger:
    """Setup the global logging configurations and instanciate a specific logger for the current script

    Parameters
    ----------
    args : dict
        The arguments given to the script

    Returns
    --------
    the logger: logger.Logger
    """
    # create logger and formatter
    logger = logging.getLogger()

    # Verbose level => logging level
    log_level = args.verbosity
    if args.verbosity >= len(LEVEL):
        log_level = len(LEVEL) - 1
        # logging.warning("verbosity level is too high, I'm gonna assume you're taking the highest (%d)" % log_level)

    # Define the default logger configuration
    logging_config = dict(
        version=1,
        disable_existing_logger=True,
        formatters={
            "f": {
                "format": "[%(asctime)s] [%(levelname)s] — [%(name)s — %(funcName)s:%(lineno)d] %(message)s",
                "datefmt": "%d/%b/%Y: %H:%M:%S ",
            }
        },
        handlers={
            "h": {
                "class": "logging.StreamHandler",
                "formatter": "f",
                "level": LEVEL[log_level],
            }
        },
        root={"handlers": ["h"], "level": LEVEL[log_level]},
    )

    # Add file handler if file logging required
    if args.log_file is not None:
        logging_config["handlers"]["f"] = {
            "class": "logging.FileHandler",
            "formatter": "f",
            "level": LEVEL[log_level],
            "filename": args.log_file,
        }
        logging_config["root"]["handlers"] = ["h", "f"]

    # Setup logging configuration
    dictConfig(logging_config)

    # Retrieve and return the logger dedicated to the script
    logger = logging.getLogger(__name__)
    return logger


def define_argument_parser() -> argparse.ArgumentParser:
    """Defines the argument parser

    Returns
    --------
    The argument parser: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(description="")

    # Add Logging dedicated options
    parser.add_argument("-l", "--log_file", default=None, help="Logger file")
    parser.add_argument(
        "-v",
        "--verbosity",
        action="count",
        default=0,
        help="increase output verbosity",
    )

    # Add tool options
    parser.add_argument(
        "-a",
        "--annotation-file",
        default="",
        type=str,
        help="The annotation file (HTK label or TextGrid)",
    )
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

    # Return parser
    return parser


def main():
    # Initialization
    arg_parser = define_argument_parser()
    args = arg_parser.parse_args()
    logger = configure_logger(args)

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

    # Check with data
    if args.coefficient_file:
        controller.loadCoefficientFile(args.coefficient_file, args.dimension, frameshift)

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
    build_gui(APP, infos, frameshift, annotation)


###############################################################################
#  Envelopping
###############################################################################
if __name__ == "__main__":
    main()
