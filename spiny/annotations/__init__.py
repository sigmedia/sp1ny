import pathlib
from .io import AnnotationSerialiser
from .io.htk_lab import HTKLabelSerialiser
from .io.textgrid import TextGridSerialiser
from .io.json import JSONSerialiser

from .control import get_controller
from . import model

__all__ = [
    "AnnotationSerialiser",
    "HTKLabelSerialiser",
    "TextGridSerialiser",
    "JSONSerialiser",
    "get_controller",
    "load_annotations",
    "model",
]


def load_annotations(annotation_file):
    get_controller().loadAnnotations(pathlib.Path(annotation_file))


def __getattr__(name):
    # Backward compatibility: "from spiny.annotations import controller" creates the controller lazily
    if name == "controller":
        return get_controller()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
