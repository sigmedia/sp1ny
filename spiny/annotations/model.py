from dataclasses import dataclass
from typing import OrderedDict

from ..core import Segment


@dataclass
class Annotation(Segment):
    label: str


@dataclass
class AnnotationSet:
    annotations: OrderedDict[str, list[Annotation]]
    ignored: set[str]
