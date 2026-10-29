from __future__ import annotations

import dataclasses
import json
import pathlib
from typing import Any

# Import abstract class
from ..model import AnnotationSet, Annotation
from . import AnnotationSerialiser


class EnhancedJSONEncoder(json.JSONEncoder):
    """JSON encoder also accepting dataclasses (as dicts) and sets (as lists)"""

    def default(self, o: Any) -> Any:
        """Convert the objects the standard encoder does not know

        Parameters
        ----------
        o : Any
            The object

        Returns
        -------
        Any
            A JSON-serialisable equivalent
        """
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)

        if isinstance(o, set):
            return list(o)

        return super().default(o)


class JSONSerialiser(AnnotationSerialiser):
    """Class to load/save annotations from/to the spiny JSON format

    The format is::

        {
          "version": 1,
          "annotations": {"<tier>": [{"start_time": 0.0, "end_time": 0.1, "label": "a"}, ...], ...},
          "ignored": ["<tier>", ...]
        }

    "version" and "ignored" are optional when loading.
    """

    VERSION = 1

    def load(self, input_file: pathlib.Path) -> AnnotationSet:
        """Annotation extraction method.

        Parameters
        ----------
        input_file : str
            The JSON file containing the annotations

        Returns
        -------
        AnnotationSet
            The loaded annotation set

        Raises
        ------
        ValueError
            If the content does not follow the format described in the class documentation
        """
        with open(input_file, encoding="utf-8") as f_in:
            json_content = json.load(f_in)

        if not isinstance(json_content, dict) or not isinstance(json_content.get("annotations"), dict):
            raise ValueError(f'"{input_file}" is not a spiny annotation file (no "annotations" object)')
        version = json_content.get("version", self.VERSION)
        if version > self.VERSION:
            raise ValueError(f'"{input_file}" uses format version {version}, only <= {self.VERSION} is supported')

        tiers = dict()
        for tier_name, json_annotations in json_content["annotations"].items():
            annotations = []
            for i, cur_json_an in enumerate(json_annotations):
                try:
                    cur_annotation = Annotation(
                        float(cur_json_an["start_time"]), float(cur_json_an["end_time"]), str(cur_json_an["label"])
                    )
                except (KeyError, TypeError, ValueError) as ex:
                    raise ValueError(f'"{input_file}": invalid annotation #{i} in tier "{tier_name}" ({ex!r})')
                annotations.append(cur_annotation)
            tiers[tier_name] = annotations

        return AnnotationSet(tiers, set(json_content.get("ignored", [])))

    def save(self, output_file: pathlib.Path, annotation_set: AnnotationSet) -> None:
        """Write the annotations in the spiny JSON format (see the class documentation)

        Parameters
        ----------
        output_file : pathlib.Path
            The file
        annotation_set : AnnotationSet
            The annotations
        """
        content = {
            "version": self.VERSION,
            "annotations": annotation_set.annotations,
            "ignored": sorted(annotation_set.ignored),
        }
        with open(output_file, "w", encoding="utf-8") as f_out:
            json.dump(content, f_out, indent=2, cls=EnhancedJSONEncoder, ensure_ascii=False)
