from .io import AnnotationLoader
from .io.htk_lab import HTKAnnotationLoader
from .io.textgrid import TGTAnnotationLoader

from .control import controller
from . import model

__all__ = ["AnnotationLoader", "HTKAnnotationLoader", "TGTAnnotationLoader", "controller", "model"]


def load_annotations(annotation_file):
    if annotation_file.endswith(".lab"):
        an_loader = HTKAnnotationLoader()
    elif annotation_file.endswith(".TextGrid"):
        an_loader = TGTAnnotationLoader()
    else:
        raise Exception("The annotation cannot be parsed, format is unknown")

    model.annotation_set = an_loader.load(annotation_file)
