import base64
import hashlib
import json
from pathlib import Path

import pytest
from conftest import load_script

fetch_chart_libs = load_script("fetch_chart_libs")

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "assets" / "template"


def _pin(payload: bytes) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(payload).digest()).decode()


def _index(echarts: bytes, mermaid: bytes, **overrides):
    doc = {
        "assets": {
            "echarts": {
                "current": "5.6.1",
                "versions": {
                    "5.6.1": {
                        "path": "report-assets/echarts-5.6.1.min.js",
                        "integrity": _pin(echarts),
                    }
                },
            },
            "mermaid": {
                "current": "11.15.0",
                "versions": {
                    "11.15.0": {
                        "path": "report-assets/mermaid-11.15.0.min.js",
                        "integrity": _pin(mermaid),
                    }
                },
            },
        }
    }
    doc["assets"].update(overrides)
    return doc


def _report_dir(tmp_path):
    report = tmp_path / "report"
    report.mkdir()
    (report / "index.html").write_text(
        "<html><script id='chart-libs-data' type='application/json'>\n"
        "<!-- CHARTLIBS-BEGIN -->null<!-- CHARTLIBS-END -->\n"
        "</script></html>",
        encoding="utf-8",
    )
    return report


def _serve(index, files, seen=None):
    def _fetch(url):
        if seen is not None:
            seen.append(url)
        if url.endswith(fetch_chart_libs.VERSIONS_DOC):
            return json.dumps(index).encode()
        for name, body in files.items():
            if url.endswith(name):
                return body
        raise fetch_chart_libs.ChartLibError(f"404 {url}")

    return _fetch


@pytest.mark.unit
def test_template_carries_no_pin_of_its_own():
    # The whole point: the producer must not hold a version or hash it cannot
    # keep in sync with what the app serves.
    app_js = (TEMPLATE_DIR / "app.js").read_text(encoding="utf-8")
    assert "sha384-" not in app_js
    assert "echarts-5" not in app_js
    # And the template must expose the block the resolve step writes into.
    index_html = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    assert "CHARTLIBS-BEGIN" in index_html


@pytest.mark.unit
def test_resolves_pins_and_vendors_bytes(tmp_path, monkeypatch):
    echarts, mermaid = b"window.echarts={};", b"window.mermaid={};"
    report = _report_dir(tmp_path)
    monkeypatch.setattr(
        fetch_chart_libs,
        "fetch",
        _serve(
            _index(echarts, mermaid),
            {"echarts-5.6.1.min.js": echarts, "mermaid-11.15.0.min.js": mermaid},
        ),
    )

    results = fetch_chart_libs.vendor_chart_libs(report_dir=report)
    assert {r["status"] for r in results} == {"downloaded"}
    assert (report / "report-assets" / "echarts-5.6.1.min.js").read_bytes() == echarts

    # The report is now pinned to exactly what the index declared.
    html = (report / "index.html").read_text(encoding="utf-8")
    payload = json.loads(html.split("CHARTLIBS-BEGIN -->")[1].split("<!--")[0])
    assert payload["libs"] == [
        {
            "global": "echarts",
            "path": "report-assets/echarts-5.6.1.min.js",
            "integrity": _pin(echarts),
        },
        {
            "global": "mermaid",
            "path": "report-assets/mermaid-11.15.0.min.js",
            "integrity": _pin(mermaid),
        },
    ]


@pytest.mark.unit
def test_follows_the_apps_current_version_without_any_local_edit(tmp_path, monkeypatch):
    # A bump on the platform is picked up here with nothing changed in this repo.
    echarts, mermaid = b"newer", b"m"
    index = _index(echarts, mermaid)
    index["assets"]["echarts"] = {
        "current": "6.0.0",
        "versions": {
            "6.0.0": {
                "path": "report-assets/echarts-6.0.0.min.js",
                "integrity": _pin(echarts),
            }
        },
    }
    report = _report_dir(tmp_path)
    monkeypatch.setattr(
        fetch_chart_libs,
        "fetch",
        _serve(
            index, {"echarts-6.0.0.min.js": echarts, "mermaid-11.15.0.min.js": mermaid}
        ),
    )

    fetch_chart_libs.vendor_chart_libs(report_dir=report)
    html = (report / "index.html").read_text(encoding="utf-8")
    assert "report-assets/echarts-6.0.0.min.js" in html
    assert (report / "report-assets" / "echarts-6.0.0.min.js").is_file()


@pytest.mark.unit
def test_refuses_bytes_that_disagree_with_the_published_integrity(tmp_path, monkeypatch):
    # The app serving something other than it advertises must fail here, not as
    # a blocked script in the reader's browser.
    echarts, mermaid = b"expected", b"m"
    report = _report_dir(tmp_path)
    monkeypatch.setattr(
        fetch_chart_libs,
        "fetch",
        _serve(
            _index(echarts, mermaid),
            {"echarts-5.6.1.min.js": b"tampered", "mermaid-11.15.0.min.js": mermaid},
        ),
    )

    with pytest.raises(fetch_chart_libs.ChartLibError, match="integrity mismatch"):
        fetch_chart_libs.vendor_chart_libs(report_dir=report)
    assert not (report / "report-assets" / "echarts-5.6.1.min.js").exists()
    assert "null" in (report / "index.html").read_text(encoding="utf-8")


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda d: d["assets"].pop("mermaid"), "does not offer"),
        (lambda d: d["assets"]["echarts"].update(current="9.9.9"), "no usable current"),
        (
            lambda d: d["assets"]["echarts"]["versions"]["5.6.1"].pop("integrity"),
            "no integrity",
        ),
        (
            lambda d: d["assets"]["echarts"]["versions"]["5.6.1"].update(
                path="echarts-latest.min.js"
            ),
            "layout",
        ),
    ],
)
def test_rejects_an_unusable_index(tmp_path, monkeypatch, mutate, match):
    # Everything the report will pin comes from this document, so validate it at
    # authoring time rather than trusting it.
    echarts, mermaid = b"e", b"m"
    index = _index(echarts, mermaid)
    mutate(index)
    report = _report_dir(tmp_path)
    monkeypatch.setattr(fetch_chart_libs, "fetch", _serve(index, {}))

    with pytest.raises(fetch_chart_libs.ChartLibError, match=match):
        fetch_chart_libs.vendor_chart_libs(report_dir=report)


@pytest.mark.unit
def test_reuses_a_vendored_copy_that_already_matches(tmp_path, monkeypatch):
    echarts, mermaid = b"e", b"m"
    report = _report_dir(tmp_path)
    monkeypatch.setattr(
        fetch_chart_libs,
        "fetch",
        _serve(
            _index(echarts, mermaid),
            {"echarts-5.6.1.min.js": echarts, "mermaid-11.15.0.min.js": mermaid},
        ),
    )
    fetch_chart_libs.vendor_chart_libs(report_dir=report)

    seen = []
    monkeypatch.setattr(
        fetch_chart_libs,
        "fetch",
        _serve(
            _index(echarts, mermaid),
            {"echarts-5.6.1.min.js": echarts, "mermaid-11.15.0.min.js": mermaid},
            seen,
        ),
    )
    results = fetch_chart_libs.vendor_chart_libs(report_dir=report)
    assert {r["status"] for r in results} == {"cached"}
    # Only the index is re-fetched; the asset bytes are not re-downloaded.
    assert seen == [f"https://www.zenable.app/{fetch_chart_libs.VERSIONS_DOC}"]


@pytest.mark.unit
def test_resolves_against_the_requested_environment(tmp_path, monkeypatch):
    echarts, mermaid = b"e", b"m"
    report = _report_dir(tmp_path)
    seen = []
    monkeypatch.setattr(
        fetch_chart_libs,
        "fetch",
        _serve(
            _index(echarts, mermaid),
            {"echarts-5.6.1.min.js": echarts, "mermaid-11.15.0.min.js": mermaid},
            seen,
        ),
    )
    fetch_chart_libs.vendor_chart_libs(report_dir=report, subdomain="staging")
    assert all(url.startswith("https://staging.zenable.app/") for url in seen), seen


@pytest.mark.unit
def test_an_already_resolved_report_survives_an_index_outage(tmp_path, monkeypatch):
    # The pin is fixed for the report's life and the bytes are on disk, so a
    # temporary outage must not fail an assessment that needs nothing new.
    echarts, mermaid = b"e", b"m"
    report = _report_dir(tmp_path)
    monkeypatch.setattr(
        fetch_chart_libs,
        "fetch",
        _serve(
            _index(echarts, mermaid),
            {"echarts-5.6.1.min.js": echarts, "mermaid-11.15.0.min.js": mermaid},
        ),
    )
    fetch_chart_libs.vendor_chart_libs(report_dir=report)
    pinned = (report / "index.html").read_text(encoding="utf-8")

    def _down(url):
        raise fetch_chart_libs.ChartLibError("503")

    monkeypatch.setattr(fetch_chart_libs, "fetch", _down)
    results = fetch_chart_libs.vendor_chart_libs(report_dir=report)

    assert {r["status"] for r in results} == {"kept"}
    # The pin is untouched — a rerun must not silently change what ships.
    assert (report / "index.html").read_text(encoding="utf-8") == pinned


@pytest.mark.unit
def test_an_unresolved_report_still_fails_when_the_index_is_down(tmp_path, monkeypatch):
    # A first resolve genuinely needs the index: nothing else knows the version.
    report = _report_dir(tmp_path)

    def _down(url):
        raise fetch_chart_libs.ChartLibError("503")

    monkeypatch.setattr(fetch_chart_libs, "fetch", _down)
    with pytest.raises(fetch_chart_libs.ChartLibError, match="503"):
        fetch_chart_libs.vendor_chart_libs(report_dir=report)


@pytest.mark.unit
def test_a_tampered_vendored_copy_is_not_accepted_offline(tmp_path, monkeypatch):
    # Falling back must still mean verified bytes, not merely present ones.
    echarts, mermaid = b"e", b"m"
    report = _report_dir(tmp_path)
    monkeypatch.setattr(
        fetch_chart_libs,
        "fetch",
        _serve(
            _index(echarts, mermaid),
            {"echarts-5.6.1.min.js": echarts, "mermaid-11.15.0.min.js": mermaid},
        ),
    )
    fetch_chart_libs.vendor_chart_libs(report_dir=report)
    (report / "report-assets" / "echarts-5.6.1.min.js").write_bytes(b"tampered")

    def _down(url):
        raise fetch_chart_libs.ChartLibError("503")

    monkeypatch.setattr(fetch_chart_libs, "fetch", _down)
    with pytest.raises(fetch_chart_libs.ChartLibError):
        fetch_chart_libs.vendor_chart_libs(report_dir=report)
