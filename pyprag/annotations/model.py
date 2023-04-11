from dataclasses import dataclass
from typing import Dict, List

from ..core import Segment


@dataclass
class Annotation(Segment):
    label: str


@dataclass
class AnnotationSet:
    annotations: Dict[str, List[Annotation]]
