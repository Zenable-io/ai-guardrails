"""Unit tests for trufflehog_to_secrets.py (trufflehog NDJSON -> secrets.json).

Run from the skill scripts dir:  uv run --with pytest pytest tests/
"""

import json
from pathlib import Path

import pytest
from conftest import load_script

ts = load_script("trufflehog_to_secrets")


def _ndjson(tmp: Path, name: str, records: list[dict]) -> Path:
    p = tmp / name
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return p


@pytest.mark.unit
def test_raw_secret_is_never_emitted(tmp_path: Path) -> None:
    rec = {
        "DetectorName": "SnykKey",
        "DetectorType": 1,
        "Verified": False,
        "Raw": "snyk-SUPER-SECRET-VALUE",
        "RawV2": "snyk-SUPER-SECRET-VALUE-v2",
        "Redacted": "snyk-****",
        "SourceName": "trufflehog - git",
        "SourceMetadata": {
            "Data": {"Git": {"file": "a.txt", "line": 11, "commit": "deadbeefcafe"}}
        },
    }
    f = _ndjson(tmp_path, "trufflehog.git.json", [rec])
    payload = ts.build_payload([f], note="")
    blob = json.dumps(payload)
    assert "SUPER-SECRET-VALUE" not in blob  # neither Raw nor RawV2 leaked
    assert payload["findings"][0]["redacted"] == "snyk-****"
    assert payload["findings"][0]["location"] == "a.txt:11 @ deadbeefca"


@pytest.mark.unit
def test_verified_and_detector_counts(tmp_path: Path) -> None:
    recs = [
        {"DetectorName": "AWS", "Verified": True, "Redacted": "AKIA****"},
        {"DetectorName": "AWS", "Verified": False, "Redacted": "AKIA****"},
        {"DetectorName": "SnykKey", "Verified": False, "Redacted": "snyk-****"},
    ]
    f = _ndjson(tmp_path, "trufflehog.git.json", recs)
    payload = ts.build_payload([f], note="")
    s = payload["summary"]
    assert s["total_findings"] == 3
    assert s["verified"] == 1 and s["unverified"] == 2
    assert s["detectors"] == {"AWS": 2, "SnykKey": 1}


@pytest.mark.unit
def test_generated_at_can_be_omitted_for_reproducible_output(tmp_path: Path) -> None:
    f = _ndjson(
        tmp_path,
        "trufflehog.git.json",
        [{"DetectorName": "SnykKey", "Verified": False, "Redacted": "x"}],
    )
    payload = ts.build_payload([f], note="", generated_at="")
    assert "generated_at" not in payload


@pytest.mark.unit
def test_scan_label_from_filename_and_empty_fs_scan(tmp_path: Path) -> None:
    fs = _ndjson(tmp_path, "trufflehog.fs.json", [])  # empty filesystem scan
    git = _ndjson(
        tmp_path,
        "trufflehog.git.json",
        [{"DetectorName": "SnykKey", "Verified": False, "Redacted": "x"}],
    )
    payload = ts.build_payload([fs, git], note="")
    scans = {s["scan"]: s for s in payload["scans"]}
    assert scans["fs"]["finding_count"] == 0
    assert scans["git"]["finding_count"] == 1
    assert payload["findings"][0]["scan"] == "git"


@pytest.mark.unit
def test_discover_skips_analyzed_siblings(tmp_path: Path) -> None:
    _ndjson(tmp_path, "trufflehog.git.json", [])
    _ndjson(tmp_path, "trufflehog.git.json.analyzed", [])  # not matched by glob anyway
    (tmp_path / "trufflehog.analyzed.json").write_text("")  # matched by glob, must skip
    found = [p.name for p in ts._discover(tmp_path)]
    assert "trufflehog.git.json" in found
    assert "trufflehog.analyzed.json" not in found


@pytest.mark.unit
def test_tolerates_blank_and_non_finding_lines(tmp_path: Path) -> None:
    p = tmp_path / "trufflehog.git.json"
    p.write_text(
        json.dumps({"DetectorName": "SnykKey", "Verified": False, "Redacted": "x"})
        + "\n\n"
        + json.dumps({"summary": "scan complete, no DetectorName here"})
        + "\nnot json at all\n"
    )
    payload = ts.build_payload([p], note="")
    assert payload["summary"]["total_findings"] == 1  # only the real finding counted
