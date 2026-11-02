import re
from dataclasses import dataclass

from ..core import Segment


def display_label(label: str) -> str:
    """Give the text to show for a label: the monophone of a full-context label ("x^y-a+b=c..." => "a")

    Parameters
    ----------
    label : str
        The label

    Returns
    -------
    str
        The text to show (the label itself if it is not a full-context one)
    """
    match = re.search("-(.+?)\\+", label)
    return match.group(1) if match else label


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
