from typing import List

import pathlib

# Textgrid utilities
import tgt

# Import abstract class
from ..model import AnnotationSet, Annotation
from . import AnnotationSerialiser

###############################################################################
# Classes
###############################################################################


class TextGridSerialiser(AnnotationSerialiser):
    """Class to load annotations from TextGrid files

    Attributes
    ----------
    segments : dict
        A dictionary whose values are list of segments. Each segment is represented by a tuple (start, end, label)

    reference : list
        The reference tier (so a list of segments!)

    """

    def load(self, input_file: pathlib.Path) -> AnnotationSet:
        """Annotation extraction method.

        Parameters
        ----------
        input_file : str
            The TextGrid file containing the annotations

        Returns
        -------
        dict
            A dictionary whose values are list of segments. Each segment is represented by a tuple (start, end, label)

        """
        self.segments = dict()
        try:
            the_tgt = tgt.io3.read_textgrid(input_file, encoding="utf-8")
        except UnicodeError:
            the_tgt = tgt.io3.read_textgrid(input_file, encoding="utf-16")

        an_dict = dict()
        for cur_tier in the_tgt.tiers:
            annotations: List[Annotation] = []

            for an in cur_tier.annotations:
                annotation: Annotation = Annotation(an.start_time, an.end_time, an.text)
                annotations.append(annotation)

            if annotations:
                an_dict[cur_tier.name] = annotations
                self.logger.debug("%s added" % cur_tier.name)
            else:
                self.logger.warning("%s is empty, we ignore it!" % cur_tier.name)

        annotation_set: AnnotationSet = AnnotationSet(an_dict, set())
        return annotation_set

    def save(self, output_file: pathlib.Path, annotation_set: AnnotationSet) -> None:
        the_textgrid = tgt.core.TextGrid()
        for tier_name, cur_tier in annotation_set.annotations.items():
            the_tier = tgt.core.IntervalTier(start_time=0, end_time=1, name=tier_name)
            for cur_annotation in cur_tier:
                the_annotation = tgt.core.Interval(
                    start_time=cur_annotation.start_time, end_time=cur_annotation.end_time, text=cur_annotation.label
                )
                the_tier.add_annotation(the_annotation)
            the_textgrid.add_tier(the_tier)
        tgt.io3.write_to_file(the_textgrid, output_file, format="long", encoding="utf8")
