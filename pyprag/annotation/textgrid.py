#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module which contains utils to load a TextGrid file. The entry class is TGTAnnotation.

LICENSE
"""
# Regular expression
import re

# Textgrid utilities
import tgt

# Import abstract class
from pyprag.annotation import AnnotationLoader

###############################################################################
# Classes
###############################################################################

class TGTAnnotation(AnnotationLoader):
    """Class to load annotations from TextGrid files

    Attributes
    ----------
    segments : dict
        A dictionary whose values are list of segments. Each segment is represented by a tuple (start, end, label)

    reference : list
        The reference tier (so a list of segments!)

    """

    def extract_annotation(self, input_file):
        """Annotation extraction method.

        Parameters
        ----------
        input_file : str
            The TextGrid file containing the annotations

        Returns
        -------
        dict
            A dictionary whose values are list of segments. Each segment is represented by a tuple (start, end, label)

        """
        self.segments = dict()
        try:
            the_tgt = tgt.io3.read_textgrid(input_file, encoding="utf-8")
        except UnicodeError:
            the_tgt = tgt.io3.read_textgrid(input_file, encoding="utf-16")

        for cur_tier in the_tgt.tiers:
            cur_tier_segments = []
            for an in cur_tier.annotations:
                cur_tier_segments.append((an.start_time, an.end_time, an.text))

            if cur_tier_segments:
                self.segments[cur_tier.name] = cur_tier_segments
                self.logger.debug("%s added" % cur_tier.name)
            else:
                self.logger.warning("%s is empty, we ignore it!" % cur_tier.name)
