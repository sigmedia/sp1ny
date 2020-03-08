import pathlib
from .io import AnnotationLoader
from .io.htk_lab import HTKAnnotationLoader
from .io.textgrid import TGTAnnotationLoader

from .control import controller
from . import model

__all__ = ["AnnotationLoader", "HTKAnnotationLoader", "TGTAnnotationLoader", "controller", "model"]


def load_annotations(annotation_file):
    controller.loadAnnotations(pathlib.Path(annotation_file))
