import pathlib
import logging

from ..model import AnnotationSet


class AnnotationSerialiser:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def load(self, input_file: pathlib.Path) -> AnnotationSet:
        raise NotImplementedError("")

    def save(self, output_file: pathlib.Path, annotations: AnnotationSet) -> None:
        raise NotImplementedError("")
