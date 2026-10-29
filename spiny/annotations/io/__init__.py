from __future__ import annotations

import logging
import pathlib

from ..model import AnnotationSet


class AnnotationSerialiser:
    """Base class of the annotation file formats: subclasses implement load and save"""

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    def load(self, input_file: pathlib.Path) -> AnnotationSet:
        """Read an annotation file

        Parameters
        ----------
        input_file : pathlib.Path
            The file

        Returns
        -------
        AnnotationSet
            The annotations
        """
        raise NotImplementedError("")

    def save(self, output_file: pathlib.Path, annotations: AnnotationSet) -> None:
        """Write an annotation file

        Parameters
        ----------
        output_file : pathlib.Path
            The file
        annotations : AnnotationSet
            The annotations
        """
        raise NotImplementedError("")
