import logging

from ..model import AnnotationSet


class AnnotationLoader:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def load(self, input_file) -> AnnotationSet:
        raise NotImplementedError("")
