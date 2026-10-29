import numpy as np


class RawDataExtractor:
    def __init__(self):
        pass

    def loadCoefficientFile(self, coefficient_file, dimension, frameshift):
        self._coefficient_file = coefficient_file
        self._dimension = dimension
        self._frameshift = frameshift

    def extract(self):
        """Load the coefficients: a headerless binary file of native-endian float32 values

        A negative dimension -d means the file stores frames of d values (shape (-1, d)),
        a positive dimension d means it stores d tracks one after the other (shape (d, -1)).

        Raises
        ------
        ValueError
            if the dimension is 0 or does not divide the number of values
        """
        if self._dimension == 0:
            raise ValueError("The dimension of the coefficient vector cannot be 0")
        data = np.fromfile(self._coefficient_file, dtype=np.float32)
        if data.size % abs(self._dimension) != 0:
            raise ValueError(
                f'"{self._coefficient_file}" contains {data.size} values, '
                + f"which is not a multiple of the dimension {abs(self._dimension)}"
            )

        if self._dimension < 0:
            self._data = data.reshape((-1, -self._dimension))
        else:
            self._data = data.reshape((self._dimension, -1)).T
        return self._data
