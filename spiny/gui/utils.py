#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

    Module containing GUI related useful functions

LICENSE
    MIT License, see the LICENSE file at the root of the repository
"""

# Linear algebra
import numpy as np

#####################################################################################################
# Functions
#####################################################################################################


def cmapToColormap(cmap, nTicks=16, alpha=255):
    """Converts a Matplotlib colormap to pyqtgraph colormap ticks.

    The colormap is sampled, so any matplotlib colormap works (listed colormaps such as 'viridis',
    segmented ones such as 'jet' and function-based ones such as 'gnuplot').

    Parameters
    ---------
    cmap : matplotlib.colors.Colormap
        The colormap (e.g. matplotlib.colormaps["viridis"])

    nTicks : int, optional
        The number of ticks to generate. (default: 16)

    alpha : int, optional
        The alpha opacity coefficient, between 0 and 255. (default: 255)

    Returns
    -------
    list
        A list of tuples. Each tuple contains the position and the color tuple in RGBA format (R, G, B, alpha)

    Raises
    ------
    ValueError
        if cmap is not a correct color map object
    """
    if not (callable(cmap) and hasattr(cmap, "N")):
        raise ValueError("[cmapToColormap] Unknown cmap format or not a cmap!")

    positions = np.linspace(0.0, 1.0, nTicks)
    rgba_colors = np.asarray(cmap(positions))  # (nTicks, 4) floats in [0, 1]
    return [
        (float(pos), (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)), alpha))
        for pos, (r, g, b, _) in zip(positions, rgba_colors)
    ]
