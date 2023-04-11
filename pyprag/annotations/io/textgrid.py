from typing import List

# Textgrid utilities
import tgt

# Import abstract class
from ..model import AnnotationSet, Annotation
from . import AnnotationLoader

###############################################################################
# Classes
###############################################################################


class TGTAnnotationLoader(AnnotationLoader):
    """Class to load annotations from TextGrid files

    Attributes
    ----------
    segments : dict
        A dictionary whose values are list of segments. Each segment is represented by a tuple (start, end, label)

    reference : list
        The reference tier (so a list of segments!)

    """

    def load(self, input_file) -> AnnotationSet:
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

        annotation_set: AnnotationSet = AnnotationSet(an_dict)
        return annotation_set
