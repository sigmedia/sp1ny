#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Package containing modules to load annotations.

LICENSE
"""

import logging


class AnnotationLoader:
    """Abstract class to regroup annotation loaders

    Attributes
    ----------
    segments : dict
        A dictionary whose values are list of segments. Each segment is represented by a tuple (start, end, label)

    reference : list
        The reference tier (so a list of segments!)
    """

    def __init__(self, input_file, wav=None, reference=None):
        """
        Parameters
        ----------
        input_file : str
            The TextGrid file containing the annotations

        reference : str
            The name of the reference tier

        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.wav = wav
        self.extract_annotation(input_file)

        if reference is None:
            reference = list(self.segments.keys())[0]

        self.reference = self.segments[reference]
        self.logger.debug("The reference tier is \"%s\"" % reference)
