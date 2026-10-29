# Regular expression
import pathlib
import re

# Import abstract class
from ..model import AnnotationSet, Annotation
from . import AnnotationSerialiser

###############################################################################
# global constants
###############################################################################

HTK_UNIT = 10000000

###############################################################################
# Classes
###############################################################################


class HTKLabelSerialiser(AnnotationSerialiser):
    """Class to load annotations from HTK Label files

    Attributes
    ----------
    segments : dict
        A dictionary (containing only one key: "default") whose values are list of segments.
        Each segment is represented by a tuple (start, end, label)

    reference : list
        The default tier (so a list of segments!)

    """

    def load(self, htk_file: str | pathlib.Path) -> AnnotationSet:
        """Annotation extraction method.

        Each non-empty line follows the HTK label format "[start [end]] label [score] ...".
        A missing end time is replaced by the start time of the next segment.

        Parameters
        ----------
        htk_file : str
            The htk label file containing the annotations

        Returns
        -------
        AnnotationSet
            An annotation set containing one tier named "default"

        Raises
        ------
        ValueError
            If a line has no start time or no label
        """
        entries: list[list] = []

        with open(htk_file, encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                elts = line.split()
                if not elts:  # Ignore blank lines
                    continue

                # Count the leading timing columns (start and optional end)
                nb_times = 0
                while nb_times < min(2, len(elts)) and re.fullmatch(r"-?\d+", elts[nb_times]):
                    nb_times += 1

                if nb_times == 0:
                    raise ValueError(f'{htk_file}:{line_number}: no start time in "{line.strip()}"')
                if len(elts) == nb_times:
                    raise ValueError(f'{htk_file}:{line_number}: no label in "{line.strip()}"')

                # Convert to seconds
                start_time = int(elts[0]) / HTK_UNIT
                end_time = int(elts[1]) / HTK_UNIT if nb_times == 2 else None
                entries.append([start_time, end_time, self._extractLabel(elts[nb_times])])

        # Fill the missing end times with the start time of the next segment
        for i, entry in enumerate(entries):
            if entry[1] is None:
                entry[1] = entries[i + 1][0] if i + 1 < len(entries) else entry[0]

        annotations: list[Annotation] = [Annotation(start, end, label) for start, end, label in entries]
        an_dict = dict()
        an_dict["default"] = annotations
        annotation_set: AnnotationSet = AnnotationSet(an_dict, set())
        return annotation_set

    @staticmethod
    def _extractLabel(label: str) -> str:
        """Extract the monophone from a full-context label (e.g. "x^y-a+b=c..." => "a"), otherwise keep the label"""
        m = re.search("-(.+?)\\+", label)
        if m:
            return m.group(1)
        return label

    def save(self, output_file: str | pathlib.Path, annotation_set: AnnotationSet) -> None:
        """Save the first visible tier as an HTK label file (HTK labels contain only one tier)

        Raises
        ------
        ValueError
            If there is no visible tier to save
        """
        tier_names = [name for name in annotation_set.annotations if name not in annotation_set.ignored]
        if not tier_names:
            raise ValueError("There is no (visible) tier to save")
        if len(tier_names) > 1:
            self.logger.warning(
                'HTK label files contain only one tier, only "%s" is saved (ignored: %s)',
                tier_names[0],
                ", ".join(tier_names[1:]),
            )

        with open(output_file, "w", encoding="utf-8") as f_out:
            for annotation in annotation_set.annotations[tier_names[0]]:
                label = "_".join(annotation.label.split()) if annotation.label.strip() else "_"
                start = round(annotation.start_time * HTK_UNIT)
                end = round(annotation.end_time * HTK_UNIT)
                f_out.write(f"{start} {end} {label}\n")
