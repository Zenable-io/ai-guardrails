"""Unit tests for collect_experiments.py (per-experiment JSON -> experiments.json).

Run from the skill scripts dir:  uv run --with pytest pytest tests/
"""

import json
from pathlib import Path

import pytest
from conftest import load_script

ce = load_script("collect_experiments")


def _exp(tmp: Path, name: str, doc: dict) -> Path:
    p = tmp / name
    p.write_text(json.dumps(doc))
    return p


@pytest.mark.unit
def test_aggregates_and_sorts_by_id(tmp_path: Path) -> None:
    a = _exp(
        tmp_path,
        "ap1.experiment.json",
        {
            "id": "AP-1",
            "name": "brute force",
            "metrics": {
                "recovered": "8/8",
                "wall_clock_s": 38.7,
                "candidate_space": 3643,
            },
        },
    )
    b = _exp(
        tmp_path,
        "ap2.experiment.json",
        {"id": "AP-2", "name": "oracle linkage", "metrics": {"recovered": "8/8"}},
    )
    payload = ce.build_payload([b, a])  # pass out of order
    assert [e["id"] for e in payload["experiments"]] == ["AP-1", "AP-2"]  # sorted
    assert payload["experiments"][0]["metrics"]["candidate_space"] == 3643


@pytest.mark.unit
def test_missing_required_field_raises(tmp_path: Path) -> None:
    bad = _exp(tmp_path, "bad.experiment.json", {"name": "no id here"})
    with pytest.raises(ValueError, match="missing required field"):
        ce.build_payload([bad])


@pytest.mark.unit
def test_duplicate_id_raises(tmp_path: Path) -> None:
    a = _exp(tmp_path, "a.experiment.json", {"id": "AP-1", "name": "x"})
    b = _exp(tmp_path, "b.experiment.json", {"id": "AP-1", "name": "y"})
    with pytest.raises(ValueError, match="duplicate experiment id"):
        ce.build_payload([a, b])


@pytest.mark.unit
def test_optional_fields_default_cleanly(tmp_path: Path) -> None:
    a = _exp(tmp_path, "a.experiment.json", {"id": "F-007", "name": "preimage"})
    payload = ce.build_payload([a])
    e = payload["experiments"][0]
    assert e["metrics"] == {} and e["evidence"] == [] and e["summary"] == ""
    assert e["command"] is None and e["ran_at"] is None


@pytest.mark.unit
def test_discover_finds_nested_experiment_json(tmp_path: Path) -> None:
    (tmp_path / "attacks").mkdir()
    _exp(tmp_path / "attacks", "ap1.experiment.json", {"id": "AP-1", "name": "x"})
    _exp(tmp_path, "other.json", {"id": "nope", "name": "not an experiment file"})
    found = [p.name for p in ce._discover(tmp_path)]
    assert found == ["ap1.experiment.json"]  # only *.experiment.json, recursively


@pytest.mark.unit
def test_inline_into_html_replaces_markers(tmp_path: Path) -> None:
    html = tmp_path / "index.html"
    html.write_text("<!-- EXPERIMENTS-BEGIN -->null<!-- EXPERIMENTS-END -->")
    ce._inline_into_html(html, {"experiments": [{"id": "AP-1"}]})
    assert '"id":"AP-1"' in html.read_text()
