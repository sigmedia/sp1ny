import json
import pathlib

import pytest

from spiny.annotations.io.htk_lab import HTKLabelSerialiser
from spiny.annotations.io.json import JSONSerialiser
from spiny.annotations.io.textgrid import TextGridSerialiser
from spiny.annotations.model import Annotation, AnnotationSet


def load_htk(tmp_path, content):
    f = tmp_path / "f.lab"
    f.write_text(content, encoding="utf-8")
    return [(a.start_time, a.end_time, a.label) for a in HTKLabelSerialiser().load(f).annotations["default"]]


@pytest.mark.parametrize(
    "content, expected",
    [
        ("0 100000 sil\n\n", [(0.0, 0.01, "sil")]),
        ("0 100000 ə\n", [(0.0, 0.01, "ə")]),
        ("0 100000 a -12.5\n100000 200000 b -3\n", [(0.0, 0.01, "a"), (0.01, 0.02, "b")]),
        ("0 a\n100000 b\n", [(0.0, 0.01, "a"), (0.01, 0.01, "b")]),
        ("0 100000 x^y-aa+b=c@1_2\n", [(0.0, 0.01, "aa")]),
    ],
)
def test_htk_load_variants(tmp_path, content, expected):
    assert load_htk(tmp_path, content) == expected


def test_htk_rejects_lines_without_timing(tmp_path):
    with pytest.raises(ValueError, match=":1:"):
        load_htk(tmp_path, "sil\n")


def test_htk_round_trip(tmp_path, example_annotations):
    HTKLabelSerialiser().save(tmp_path / "o.lab", example_annotations)
    assert HTKLabelSerialiser().load(tmp_path / "o.lab") == example_annotations


def test_htk_save_requires_a_visible_tier(tmp_path):
    with pytest.raises(ValueError):
        HTKLabelSerialiser().save(tmp_path / "o.lab", AnnotationSet({"t": []}, {"t"}))


def test_json_round_trip(tmp_path):
    annotation_set = AnnotationSet({"t": [Annotation(0.0, 1.0, "ə")], "u": []}, {"u"})
    JSONSerialiser().save(tmp_path / "o.json", annotation_set)
    content = json.loads((tmp_path / "o.json").read_text(encoding="utf-8"))
    assert content["version"] == JSONSerialiser.VERSION
    assert JSONSerialiser().load(tmp_path / "o.json") == annotation_set


@pytest.mark.parametrize(
    "content, error",
    [
        ({"annotations": {"t": [{"start_time": 0, "label": "a"}]}}, "invalid annotation #0"),
        ([1, 2], "not a spiny annotation file"),
        ({"version": 99, "annotations": {}}, "version 99"),
    ],
)
def test_json_invalid_content(tmp_path, content, error):
    (tmp_path / "a.json").write_text(json.dumps(content))
    with pytest.raises(ValueError, match=error):
        JSONSerialiser().load(tmp_path / "a.json")


def test_json_ignored_is_optional(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"annotations": {"t": []}}))
    assert JSONSerialiser().load(tmp_path / "a.json").ignored == set()


def test_textgrid_round_trip(tmp_path, example_annotations):
    TextGridSerialiser().save(str(tmp_path / "o.TextGrid"), example_annotations)
    loaded = TextGridSerialiser().load(str(tmp_path / "o.TextGrid"))
    assert [a.label for a in loaded.annotations["default"]] == [
        a.label for a in example_annotations.annotations["default"]
    ]


def test_serialiser_for_extension(qapp):
    from spiny.annotations.control import serialiser_for

    assert isinstance(serialiser_for(pathlib.Path("a.textgrid")), TextGridSerialiser)
    assert isinstance(serialiser_for(pathlib.Path("a.lab")), HTKLabelSerialiser)
    with pytest.raises(ValueError):
        serialiser_for(pathlib.Path("a.wav"))
