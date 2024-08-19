from dataclasses import dataclass
from typing import OrderedDict

from spiny.ui.segment import Segment


@dataclass
class Annotation(Segment):
    label: str


@dataclass
class AnnotationSet:
    annotations: OrderedDict[str, list[Annotation]]
    ignored: set[str]
