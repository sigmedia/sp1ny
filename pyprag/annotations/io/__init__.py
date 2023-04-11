from ..model import AnnotationSet


class AnnotationLoader:
    def load(self, input_file) -> AnnotationSet:
        raise NotImplementedError("")
