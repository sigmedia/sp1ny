#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

LICENSE
    This script is in the public domain, free from copyrights or restrictions.
    Created:  6 March 2020
"""

# Logging
import logging

# Regular expression
import re

# Textgrid utilities
import tgt

class TGTAlignment:
    def __init__(self, input_file, wav=None, reference=None):
        self.logger = logging.getLogger("TGTAlignment")
        self.wav = wav
        self.__extract_alignment(input_file)

        if reference is None:
            reference = list(self.segments.keys())[0]

        self.reference = self.segments[reference]
        self.logger.debug("The reference tier is \"%s\"" % reference)

    def __extract_alignment(self, input_file):
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
