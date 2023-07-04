# Regular expression
import re
from typing import List

# Import abstract class
from ..model import AnnotationSet, Annotation
from . import AnnotationLoader

###############################################################################
# global constants
###############################################################################

HTK_UNIT = 10000000

###############################################################################
# Classes
###############################################################################


class HTKAnnotationLoader(AnnotationLoader):
    """Class to load annotations from HTK Label files

    Attributes
    ----------
    segments : dict
        A dictionary (containing only one key: "default") whose values are list of segments.
        Each segment is represented by a tuple (start, end, label)

    reference : list
        The default tier (so a list of segments!)

    """

    def load(self, htk_file) -> AnnotationSet:
        """Annotation extraction method.

        Parameters
        ----------
        htk_file : str
            The htk label file containing the annotations

        Returns
        -------
        dict
            A dictionary whose values are list of segments. Each segment is represented by a tuple (start, end, label)

        Raises
        ------
        NotImplementedError
            If the label is not correctly formatted
        """
        annotations: List[Annotation] = []

        with open(htk_file) as f:
            for line in f:
                # Preprocess
                line = line.strip()
                elts = line.split()
                assert len(elts) == 3

                # Convert to seconds
                start_time = int(elts[0]) / HTK_UNIT
                end_time = int(elts[1]) / HTK_UNIT

                # Extract monophone label
                m = re.search("-(.+?)\\+", elts[2])
                if m:
                    label = m.group(1)
                else:
                    m = re.search("([a-zA-Z][a-zA-Z0-9]*)$", elts[2])
                    if m:
                        label = m.group(1)
                    else:
                        raise NotImplementedError("label not correct : " + elts[2])

                # Finalize by adding everything to the list
                annotation: Annotation = Annotation(start_time, end_time, label)
                annotations.append(annotation)

        an_dict = dict()
        an_dict["default"] = annotations
        annotation_set: AnnotationSet = AnnotationSet(an_dict)
        return annotation_set
