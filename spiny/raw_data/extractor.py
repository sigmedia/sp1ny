import numpy as np


class RawDataExtractor:
    def __init__(self):
        pass

    def loadCoefficientFile(self, coefficient_file, dimension, frameshift):
        self._coefficient_file = coefficient_file
        self._dimension = dimension
        self._frameshift = frameshift

    def extract(self):
        self._data = np.fromfile(self._coefficient_file, dtype=np.float32)
        if self._dimension < 0:
            self._data = self._data.reshape((-1, -self._dimension))
        else:
            self._data = self._data.reshape((self._dimension, -1)).T
        return self._data
