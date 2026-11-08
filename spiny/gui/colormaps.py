"""Colormaps available for the data plots, without depending on matplotlib

The perceptually uniform colormaps (viridis, plasma, inferno, magma, cividis) are the ones bundled
with pyqtgraph. The sequential ones (binary, gray, bone, hot, copper) are defined below from the
piecewise-linear segment data of matplotlib, so they look exactly the same.

Notes
-----
pyqtgraph ships the original cividis table (Nuñez et al., 2018), while matplotlib uses a slightly
revised one: the darkest blues differ by up to about 20/255.
"""

from __future__ import annotations


import copy

import numpy as np
import pyqtgraph as pg

#: Gradient ticks: (position in [0, 1], RGBA color) pairs, as used by pyqtgraph's GradientEditorItem
type Ticks = list[tuple[float, tuple[int, int, int, int]]]

#: Colormaps bundled with pyqtgraph
BUNDLED_COLORMAPS = ("viridis", "plasma", "inferno", "magma", "cividis")

#: Piecewise-linear colormaps: for each channel, a list of (position, value) with values in [0, 1]
#: (taken from matplotlib's _cm.py segment data)
SEGMENTED_COLORMAPS = {
    "binary": {
        "red": [(0.0, 1.0), (1.0, 0.0)],
        "green": [(0.0, 1.0), (1.0, 0.0)],
        "blue": [(0.0, 1.0), (1.0, 0.0)],
    },
    "gray": {
        "red": [(0.0, 0.0), (1.0, 1.0)],
        "green": [(0.0, 0.0), (1.0, 1.0)],
        "blue": [(0.0, 0.0), (1.0, 1.0)],
    },
    "bone": {
        "red": [(0.0, 0.0), (0.746032, 0.652778), (1.0, 1.0)],
        "green": [(0.0, 0.0), (0.365079, 0.319444), (0.746032, 0.777778), (1.0, 1.0)],
        "blue": [(0.0, 0.0), (0.365079, 0.444444), (1.0, 1.0)],
    },
    "hot": {
        "red": [(0.0, 0.0416), (0.365079, 1.0), (1.0, 1.0)],
        "green": [(0.0, 0.0), (0.365079, 0.0), (0.746032, 1.0), (1.0, 1.0)],
        "blue": [(0.0, 0.0), (0.746032, 0.0), (1.0, 1.0)],
    },
    "copper": {
        "red": [(0.0, 0.0), (0.809524, 1.0), (1.0, 1.0)],
        "green": [(0.0, 0.0), (1.0, 0.7812)],
        "blue": [(0.0, 0.0), (1.0, 0.4975)],
    },
}

#: Names of all the available colormaps, in the order they are proposed in the GUI
COLORMAP_NAMES = BUNDLED_COLORMAPS + tuple(SEGMENTED_COLORMAPS)


def get_colormap(name: str, inverse: bool = False) -> pg.ColorMap:
    """Build the colormap of the given name

    Parameters
    ----------
    name : str
        The colormap name (one of `COLORMAP_NAMES`)
    inverse : bool, optional
        True to reverse the colormap. (default: False)

    Returns
    -------
    pg.ColorMap
        The colormap

    Raises
    ------
    ValueError
        if the name is unknown
    """
    if name in BUNDLED_COLORMAPS:
        cmap = pg.colormap.get(name)
    elif name in SEGMENTED_COLORMAPS:
        # Evaluate every channel at all the breakpoints, so that pyqtgraph's linear interpolation is exact
        channels = SEGMENTED_COLORMAPS[name]
        positions = np.unique([pos for segments in channels.values() for pos, _ in segments])
        colors = np.stack(
            [
                np.interp(positions, [pos for pos, _ in channels[channel]], [value for _, value in channels[channel]])
                for channel in ("red", "green", "blue")
            ],
            axis=1,
        )
        cmap = pg.ColorMap(positions, np.rint(colors * 255).astype(np.uint8))
    else:
        raise ValueError(f'Unknown colormap "{name}", available colormaps are: {", ".join(COLORMAP_NAMES)}')

    if inverse:
        cmap = copy.copy(cmap)  # NOTE: pyqtgraph caches its colormaps: reversing one in place would change the cache
        cmap.reverse()
    return cmap


def colormap_ticks(name: str, inverse: bool = False, nb_ticks: int = 10) -> Ticks:
    """Sample a colormap as gradient ticks (the format used by pyqtgraph's GradientEditorItem.restoreState)

    Parameters
    ----------
    name : str
        The colormap name (one of `COLORMAP_NAMES`)
    inverse : bool, optional
        True to reverse the colormap. (default: False)
    nb_ticks : int, optional
        The number of ticks. (default: 10)

    Returns
    -------
    list(tuple(float, tuple(int, int, int, int)))
        The (position, RGBA color) ticks, positions going from 0 to 1
    """
    lut = get_colormap(name, inverse).getLookupTable(0.0, 1.0, nb_ticks, alpha=True)
    positions = np.linspace(0.0, 1.0, nb_ticks)
    return [(float(pos), (int(r), int(g), int(b), int(a))) for pos, (r, g, b, a) in zip(positions, lut)]
