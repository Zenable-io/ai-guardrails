"""Unit tests for sbom_to_dependencies.py (syft/grype -> dependencies.json).

Run from the skill scripts dir:  uv run --with pytest pytest tests/
"""

import json
from pathlib import Path

import pytest
from conftest import load_script

sd = load_script("sbom_to_dependencies")


def _syft(target: str, artifacts: list[dict]) -> dict:
    return {
        "descriptor": {"name": "syft", "version": "1.44.0"},
        "source": {"type": "directory", "target": target},
        "artifacts": artifacts,
    }


def _grype(target: str, matches: list[dict]) -> dict:
    return {
        "descriptor": {"name": "grype", "version": "0.110.0"},
        "source": {"type": "directory", "target": target},
        "matches": matches,
    }


def _write(tmp: Path, name: str, doc: dict) -> Path:
    p = tmp / name
    p.write_text(json.dumps(doc))
    return p


@pytest.mark.unit
def test_components_dedupe_across_scans_and_merge_targets(tmp_path: Path) -> None:
    a = {
        "name": "junit",
        "version": "4.11",
        "type": "java-archive",
        "language": "java",
        "licenses": [{"spdxExpression": "EPL-1.0"}],
        "purl": "pkg:maven/junit/junit@4.11",
    }
    # Same component appears in both the dist jar and the source tree.
    dist = _write(tmp_path, "dist.syft.json", _syft("dist.jar", [a]))
    src = _write(
        tmp_path,
        "src.syft.json",
        _syft(
            ".",
            [
                a,
                {
                    "name": "guava",
                    "version": "32.0",
                    "type": "java-archive",
                    "language": "java",
                    "licenses": [{"value": "Apache-2.0"}],
                    "purl": "pkg:maven/guava@32.0",
                },
            ],
        ),
    )

    payload = sd.build_payload([dist, src], [], note="")
    assert payload["summary"]["component_count"] == 2  # junit deduped, guava unique
    junit = next(c for c in payload["components"] if c["name"] == "junit")
    assert sorted(junit["targets"]) == [".", "dist.jar"]  # both scan targets merged
    assert junit["licenses"] == ["EPL-1.0"]


@pytest.mark.unit
def test_components_have_null_resolved_license_fields(tmp_path: Path) -> None:
    art = {
        "name": "guava",
        "version": "32.0",
        "type": "java-archive",
        "licenses": [],
    }
    src = _write(tmp_path, "s.syft.json", _syft(".", [art]))
    payload = sd.build_payload([src], [], note="")
    c = payload["components"][0]
    assert c["resolved_license"] is None
    assert c["license_source"] is None


@pytest.mark.unit
def test_license_resolution_enriches_components(tmp_path: Path) -> None:
    art = {
        "name": "commons-io",
        "version": "2.16.1",
        "type": "java-archive",
        "licenses": [],
    }
    src = _write(tmp_path, "s.syft.json", _syft(".", [art]))
    licenses = tmp_path / "licenses.json"
    licenses.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "type": "license",
                        "provenance": {
                            "sourcePomRel": "org/apache/commons/commons-parent.pom"
                        },
                        "data": {
                            "component": "commons-io",
                            "version": "2.16.1",
                            "verified": ["Apache-2.0"],
                            "resolved": ["Apache-2.0"],
                            "via": "parent-pom",
                        },
                    }
                ]
            }
        )
    )

    payload = sd.build_payload([src], [], note="", license_resolution=licenses)

    c = payload["components"][0]
    assert c["detected_licenses"] == []
    assert c["verified_licenses"] == ["Apache-2.0"]
    assert c["resolved_licenses"] == ["Apache-2.0"]
    assert c["license_source"] == "org/apache/commons/commons-parent.pom"
    assert payload["licenses"] == [{"license": "Apache-2.0", "count": 1}]


@pytest.mark.unit
def test_license_counts_sorted_by_frequency(tmp_path: Path) -> None:
    arts = [
        {
            "name": "a",
            "version": "1",
            "type": "java-archive",
            "licenses": [{"value": "Apache-2.0"}],
        },
        {
            "name": "b",
            "version": "1",
            "type": "java-archive",
            "licenses": [{"value": "Apache-2.0"}],
        },
        {"name": "c", "version": "1", "type": "java-archive", "licenses": []},
    ]
    src = _write(tmp_path, "s.syft.json", _syft(".", arts))
    payload = sd.build_payload([src], [], note="")
    licenses = {lc["license"]: lc["count"] for lc in payload["licenses"]}
    assert licenses["Apache-2.0"] == 2
    assert licenses["(none detected)"] == 1
    # "(none detected)" is excluded from the headline license_count.
    assert payload["summary"]["license_count"] == 1


@pytest.mark.unit
def test_grype_vulns_and_result_summary(tmp_path: Path) -> None:
    matches = [
        {
            "vulnerability": {
                "id": "GHSA-x",
                "severity": "Medium",
                "fix": {"versions": ["4.13.1"], "state": "fixed"},
                "dataSource": "https://example/GHSA-x",
            },
            "artifact": {"name": "junit", "version": "4.11"},
        }
    ]
    g = _write(tmp_path, "src.grype.json", _grype(".", matches))
    payload = sd.build_payload([], [g], note="")
    assert payload["summary"]["vulnerability_count"] == 1
    v = payload["vulnerabilities"][0]
    assert (v["id"], v["package"], v["fixed_in"]) == ("GHSA-x", "junit", "4.13.1")
    assert payload["scans"][0]["result"] == "1 finding(s) — 1 Medium"


@pytest.mark.unit
def test_no_vulns_reports_clean(tmp_path: Path) -> None:
    g = _write(tmp_path, "src.grype.json", _grype(".", []))
    payload = sd.build_payload([], [g], note="")
    assert payload["scans"][0]["result"] == "No vulnerabilities found"
    assert payload["summary"]["vulnerability_count"] == 0


@pytest.mark.unit
def test_discover_skips_cdx_and_spdx_reencodings(tmp_path: Path) -> None:
    for n in ["x.syft.json", "x.syft.cdx.json", "x.syft.spdx.json"]:
        _write(tmp_path, n, _syft(".", []))
    found = sd._discover(tmp_path, "syft")
    assert [p.name for p in found] == ["x.syft.json"]  # only the native syft-json


@pytest.mark.unit
def test_inline_into_html_escapes_and_replaces(tmp_path: Path) -> None:
    html = tmp_path / "index.html"
    html.write_text(
        '<script id="dependencies-data" type="application/json">'
        "<!-- DEPENDENCIES-BEGIN -->null<!-- DEPENDENCIES-END --></script>"
    )
    sd._inline_into_html(html, {"note": "x <b>y", "components": []})
    out = html.read_text()
    assert "\\u003cb" in out  # < escaped so payload can't break out of <script>
    assert "DEPENDENCIES-BEGIN" in out
