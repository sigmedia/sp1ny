from __future__ import annotations

import os

import numpy as np


class RawDataExtractor:
    """Loader of raw coefficient files (headerless binary float32)

    The file is memory-mapped instead of read: the data is only paged in from disk when it is
    displayed, and the operating system can drop it again under memory pressure, so even very large
    coefficient files cost (almost) no resident memory.

    Attributes
    ----------
    _data : np.ndarray
        The coefficients (a read-only memory map), shape (nb_frames, dimension)
    """

    def __init__(self) -> None:
        self._data: np.ndarray = np.zeros((0, 1), dtype=np.float32)

    def loadCoefficientFile(self, coefficient_file: str, dimension: int, frameshift: float) -> None:
        """Define the coefficient file to load (it is read by `extract`)

        Parameters
        ----------
        coefficient_file : str
            The coefficient file
        dimension : int
            The dimension of a coefficient vector, see `extract`
        frameshift : float
            The frameshift in milliseconds
        """
        self._coefficient_file = coefficient_file
        self._dimension = dimension
        self._frameshift = frameshift

    def release(self) -> None:
        """Free the extracted data (the plugin is not displayed anymore)"""
        self._data = np.zeros((0, 1), dtype=np.float32)  # also closes the memory map

    def extract(self) -> np.ndarray:
        """Load the coefficients: a headerless binary file of native-endian float32 values

        A negative dimension -d means the file stores frames of d values (shape (-1, d)),
        a positive dimension d means it stores d tracks one after the other (shape (d, -1)).

        Returns
        -------
        np.ndarray
            The coefficients, shape (nb_frames, dimension), memory-mapped read-only

        Raises
        ------
        ValueError
            if the dimension is 0 or does not divide the number of values
        """
        if self._dimension == 0:
            raise ValueError("The dimension of the coefficient vector cannot be 0")

        nb_values = os.path.getsize(self._coefficient_file) // np.dtype(np.float32).itemsize
        if nb_values % abs(self._dimension) != 0:
            raise ValueError(
                f'"{self._coefficient_file}" contains {nb_values} values, '
                + f"which is not a multiple of the dimension {abs(self._dimension)}"
            )

        # NOTE: an empty file cannot be memory-mapped
        if nb_values == 0:
            data = np.zeros(0, dtype=np.float32)
        else:
            data = np.memmap(self._coefficient_file, dtype=np.float32, mode="r", shape=(nb_values,))

        if self._dimension < 0:
            self._data = data.reshape((-1, -self._dimension))
        else:
            self._data = data.reshape((self._dimension, -1)).T
        return self._data
