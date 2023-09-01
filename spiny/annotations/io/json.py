from collections import OrderedDict
import pathlib
import dataclasses
import json

# Import abstract class
from ..model import AnnotationSet, Annotation
from . import AnnotationSerialiser


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)

        if isinstance(o, set):
            return list(o)

        return super().default(o)


class JSONSerialiser(AnnotationSerialiser):
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
        with open(input_file) as f_in:
            json_content = json.load(f_in)

        tiers = OrderedDict()
        for tier_name, json_annotations in json_content["annotations"].items():
            annotations = []
            for cur_json_an in json_annotations:
                cur_annotation = Annotation(cur_json_an["start_time"], cur_json_an["end_time"], cur_json_an["label"])
                annotations.append(cur_annotation)
            tiers[tier_name] = annotations

        return AnnotationSet(tiers, set(json_content["ignored"]))

    def save(self, output_file: pathlib.Path, annotation_set: AnnotationSet) -> None:
        # Generat
        with open(output_file, "w") as f_out:
            json.dump(annotation_set, f_out, indent=2, cls=EnhancedJSONEncoder)
