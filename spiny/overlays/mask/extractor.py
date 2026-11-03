"""The transparency mask: a matrix of coefficients between 0 and 1, read from a numpy file"""

from __future__ import annotations

import os

import numpy as np


def load_mask(filename: str | os.PathLike) -> np.ndarray:
    """Read a mask, without loading it in memory: it can be much larger than what is displayed

    Parameters
    ----------
    filename : str or pathlib.Path
        The numpy file (.npy)

    Returns
    -------
    np.ndarray
        The coefficients (a read-only memory map), shape (nb_frames, nb_bins)

    Raises
    ------
    ValueError
        if the file does not contain a matrix of numbers between 0 and 1
    OSError
        if the file cannot be read
    """
    # NOTE: never pickled data: reading it could run any code
    mask = np.load(filename, mmap_mode="r", allow_pickle=False)
    if not isinstance(mask, np.ndarray) or mask.ndim != 2:
        raise ValueError(f"A mask must be a matrix (frames × frequency bins), got the shape {np.shape(mask)}")
    if mask.dtype.kind not in "fiub":
        raise ValueError(f"A mask must contain numbers, got the type {mask.dtype}")
    if mask.size == 0:
        raise ValueError("The mask is empty")
    low, high = mask.min(), mask.max()  # NOTE: NaN makes both comparisons false
    if not (low >= 0 and high <= 1):
        raise ValueError(f"The coefficients of a mask must be between 0 and 1, got {low} to {high}")
    return mask


def mask_image(
    mask: np.ndarray,
    first: int,
    last: int,
    stride: int,
    bin_stride: int,
    color: tuple[int, int, int],
    strength: float,
    invert: bool = False,
) -> np.ndarray:
    """Build the image covering what the mask hides: the spectrogram below shows through as much as its opacity

    Parameters
    ----------
    mask : np.ndarray
        The opacities, shape (nb_frames, nb_bins)
    first : int
        The first frame
    last : int
        The frame after the last one
    stride : int
        The step between two frames of the image
    bin_stride : int
        The step between two frequency bins of the image
    color : tuple(int, int, int)
        The red, green and blue of what is seen where the opacity is 0
    strength : float
        How much the mask applies, between 0 and 1
    invert : bool, optional
        True if the coefficients are how much is hidden, and not the opacity. (default: False)

    Returns
    -------
    np.ndarray
        The image, shape (nb_columns, nb_rows, 4), dtype uint8, the alpha channel being 255 where it hides everything
    """
    # shortcut: the frames between two columns are skipped and not averaged, average them if thin details get lost
    opacities = np.asarray(mask[first:last:stride, ::bin_stride], dtype=np.float32)
    image = np.empty((*opacities.shape, 4), dtype=np.uint8)
    image[..., :3] = color
    hidden = opacities if invert else 1.0 - opacities
    image[..., 3] = np.rint(hidden * strength * 255.0)
    return image
