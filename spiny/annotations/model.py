from dataclasses import dataclass

from ..core import Segment


@dataclass(slots=True)
class Annotation(Segment):
    """A labelled time segment

    Attributes
    ----------
    label : str
        The label of the segment
    """

    label: str


@dataclass
class AnnotationSet:
    """A set of annotation tiers

    Attributes
    ----------
    annotations : dict[str, list[Annotation]]
        The tiers (name => annotations sorted by start time), in display order
    ignored : set[str]
        The names of the hidden tiers
    """

    annotations: dict[str, list[Annotation]]
    ignored: set[str]
