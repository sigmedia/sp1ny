from __future__ import annotations

import pathlib
from typing import Any

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


def load_annotations(annotation_file: str | pathlib.Path) -> None:
    """Load an annotation file in the annotation controller (see ControlLayout.loadAnnotations)

    Parameters
    ----------
    annotation_file : str or pathlib.Path
        The annotation file (TextGrid, HTK label or JSON)
    """
    get_controller().loadAnnotations(pathlib.Path(annotation_file))


def __getattr__(name: str) -> Any:
    """Create the annotation controller lazily when `spiny.annotations.controller` is accessed

    Parameters
    ----------
    name : str
        The requested attribute

    Returns
    -------
    ControlLayout
        The annotation controller, for name == "controller"

    Raises
    ------
    AttributeError
        for any other name
    """
    # Backward compatibility: "from spiny.annotations import controller" creates the controller lazily
    if name == "controller":
        return get_controller()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
