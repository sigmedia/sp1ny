#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Command line entry point of Sp1NY: parses the options, loads the inputs and starts the GUI.

LICENSE
    MIT License, see the LICENSE file at the root of the repository
    Created: 17 January 2023
"""

# System/default
import os
from typing import Any

# Arguments
import argparse

# Messaging/logging
import logging
from logging.config import dictConfig

# PyQtGraph
from pyqtgraph.Qt import QtWidgets

# SpINY
from spiny.annotations import load_annotations
from spiny.ui import build_gui
from spiny.core import player

###############################################################################
# global constants
###############################################################################
LEVEL = [logging.WARNING, logging.INFO, logging.DEBUG]


###############################################################################
# Functions
###############################################################################
def configure_logger(args: argparse.Namespace) -> logging.Logger:
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
    logging_config: dict[str, Any] = dict(
        version=1,
        # NOTE: keep the loggers created at import time (e.g. the player's), otherwise their messages are lost
        disable_existing_loggers=False,
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
    parser = argparse.ArgumentParser(description="Sp1NY - Speech vIsualisation and aNnotation in pYthon")

    # Add Logging dedicated options
    # NOTE: the underscore spellings are kept for backward compatibility
    parser.add_argument("-l", "--log-file", "--log_file", dest="log_file", default=None, help="Logger file")
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
        help="The annotation file (HTK label, TextGrid or JSON)",
    )
    parser.add_argument(
        "-c",
        "--coefficient-file",
        default="",
        type=str,
        help="The coefficient file (headerless binary float32, requires --dimension)",
    )
    parser.add_argument(
        "-d",
        "--dimension",
        default=0,
        type=int,
        help="The dimension of the coefficient vector (negative shape is assumed to be (-1, d), positive (d, -1))",
    )
    parser.add_argument("-f", "--frameshift", default=5, type=float, help="The frameshift in milliseconds")
    parser.add_argument("--dark", action="store_true", help="Use the dark theme")
    parser.add_argument(
        "-w",
        "--wav-file",
        "--wav_file",
        dest="wav_file",
        default="",
        type=str,
        help="The audio file (if not given, a file dialog asks for it at startup)",
    )

    # Return parser
    return parser


def ask_audio_file() -> str:
    """Ask the user for the audio file to open (used when no file is given on the command line)

    Returns
    -------
    str
        The selected file, or an empty string if the dialog was cancelled
    """
    filename, _ = QtWidgets.QFileDialog.getOpenFileName(
        None,
        "Sp1NY - Open an audio file",
        "",
        "Audio files (*.wav *.flac *.ogg *.aif *.aiff *.mp3);;All files (*)",
    )
    return filename


def main() -> None:
    """Entry point of the spiny command (and of the standalone application)"""
    # Initialization
    arg_parser = define_argument_parser()
    args = arg_parser.parse_args()
    for option, filename in [
        ("--wav-file", args.wav_file),
        ("--annotation-file", args.annotation_file),
        ("--coefficient-file", args.coefficient_file),
    ]:
        if filename and not os.path.isfile(filename):
            arg_parser.error(f'{option}: "{filename}" does not exist or is not a file')
    if args.coefficient_file and args.dimension == 0:
        arg_parser.error("--dimension (-d) is required (and cannot be 0) when a coefficient file is given")
    logger = configure_logger(args)

    # Create the application before any widget (controllers and plugins are created lazily)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["SpINY"])

    # Without a file on the command line (e.g. the application was started from a file manager), ask for it
    if not args.wav_file:
        args.wav_file = ask_audio_file()
        if not args.wav_file:
            return

    # Load waves
    logger.info("Loading wav")
    player.loadNewWav(args.wav_file)

    # Check with data
    if args.coefficient_file:
        from spiny.raw_data import controller

        controller.loadCoefficientFile(args.coefficient_file, args.dimension, args.frameshift)

    # Load annotation
    logger.info("Load annotation")
    if args.annotation_file != "":
        load_annotations(args.annotation_file)

    # Generate window
    logger.info("Rendering")
    build_gui(app, args.dark)


###############################################################################
#  Envelopping
###############################################################################
if __name__ == "__main__":
    main()
