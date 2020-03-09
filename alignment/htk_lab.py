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

class HTKAlignment:
    def __init__(self, htk_file, wav=None):
        self.wav = wav
        self.__extract_alignment(htk_file)

    def __extract_alignment(self, htk_file):
        self.segments = []
        with open(htk_file) as f:
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
                self.segments.append(elts)
