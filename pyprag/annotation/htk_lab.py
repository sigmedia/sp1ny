#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module which contains utils to load a HTK Label file. The entry class is HTKAnnotation.

LICENSE
"""

# Linear algebra
import numpy as np

# Regular expression
import re

# Import abstract class
from pyprag.annotation import AnnotationLoader

###############################################################################
# global constants
###############################################################################

HTK_UNIT = 10000000

###############################################################################
# Classes
###############################################################################

class HTKAnnotation(AnnotationLoader):
    """Class to load annotations from HTK Label files

    Attributes
    ----------
    segments : dict
        A dictionary (containing only one key: "default") whose values are list of segments. Each segment is represented by a tuple (start, end, label)

    reference : list
        The default tier (so a list of segments!)

    """

    def extract_annotation(self, htk_file):
        """Annotation extraction method.

        Parameters
        ----------
        htk_file : str
            The htk label file containing the annotations

        Returns
        -------
        dict
            A dictionary whose values are list of segments. Each segment is represented by a tuple (start, end, label)

        Raises
        ------
        NotImplementedError
            If the label is not correctly formatted
        """
        self.segments = dict()
        self.segments["default"] = []
        with open(htk_file) as f:
            for l in f:
                # Preprocess
                l = l.strip()
                elts = l.split()
                assert len(elts) == 3

                # Convert to seconds
                elts[0] = int(elts[0]) / HTK_UNIT
                elts[1] = int(elts[1]) / HTK_UNIT

                # Extract monophone label
                m = re.search('-(.+?)\+', elts[2])
                if m:
                    elts[2] = m.group(1)
                else:
                    m = re.search('([a-zA-Z][a-zA-Z0-9]*)$', elts[2])
                    if m:
                        elts[2] = m.group(1)
                    else:
                        raise NotImplementedError("label not correct : " + elts[2])

                # Finalize by adding everything to the list
                self.segments["default"].append(elts)
