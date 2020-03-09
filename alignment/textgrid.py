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

# Linear algebra
import numpy as np

# Regular expression
import re

import tgt

class TGTAlignment:
    def __init__(self, input_file, wav=None, reference=None):
        self.wav = wav
        self.__extract_alignment(input_file)

        if reference is not None:
            self.reference = self.segments[reference]
        else: # Select a random tier!
            self.reference = self.segments[list(self.segments.keys())[0]]

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
            self.segments[cur_tier.name] = cur_tier_segments
