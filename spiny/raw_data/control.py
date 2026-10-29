from __future__ import annotations

from spiny.core import DataController
from .extractor import RawDataExtractor
from .visualisation import RawDataPlotWidget


class RawDataController(DataController):
    """Controller of the "Raw DATA" plugin, rendering precomputed coefficients

    Parameters
    ----------
    extractor : RawDataExtractor
        The coefficient loader
    widget : RawDataPlotWidget
        The widget rendering the coefficients
    """

    def __init__(self, extractor: RawDataExtractor, widget: RawDataPlotWidget) -> None:
        super().__init__("Raw DATA", extractor, widget)

    def loadCoefficientFile(self, coefficient_file: str, dimension: int, frameshift: float) -> None:
        """Define the coefficient file to render, see RawDataExtractor.loadCoefficientFile

        Parameters
        ----------
        coefficient_file : str
            The coefficient file
        dimension : int
            The dimension of a coefficient vector (negative: (-1, d) layout, positive: (d, -1) layout)
        frameshift : float
            The frameshift in milliseconds
        """
        self._extractor.loadCoefficientFile(coefficient_file, dimension, frameshift)
