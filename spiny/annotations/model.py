from dataclasses import dataclass
from typing import OrderedDict, List, Set

from ..core import Segment


@dataclass
class Annotation(Segment):
    label: str


@dataclass
class AnnotationSet:
    annotations: OrderedDict[str, List[Annotation]]
    ignored: Set[str]
