import pathlib
from .io import AnnotationSerialiser
from .io.htk_lab import HTKLabelSerialiser
from .io.textgrid import TextGridSerialiser
from .io.json import JSONSerialiser

from .control import controller
from . import model

__all__ = ["AnnotationSerialiser", "HTKLabelSerialiser", "TextGridSerialiser", "JSONSerialiser", "controller", "model"]


def load_annotations(annotation_file):
    controller.loadAnnotations(pathlib.Path(annotation_file))
