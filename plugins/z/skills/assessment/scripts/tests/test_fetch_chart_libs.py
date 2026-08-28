import base64
import hashlib
from pathlib import Path

import pytest
from conftest import load_script

fetch_chart_libs = load_script("fetch_chart_libs")

TEMPLATE_APP_JS = (
    Path(__file__).resolve().parents[2] / "assets" / "template" / "app.js"
)


def _pin(payload: bytes) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(payload).digest()).decode()


def _app_js(payload: bytes, *, file: str = "echarts-5.6.1.min.js") -> str:
    return f"""
  const CHART_LIBS = [
    {{
      global: "echarts",
      file: "{file}",
      integrity:
        "{_pin(payload)}",
    }},
  ];
"""


@pytest.mark.unit
def test_parses_the_real_template_pins():
    # The pins live in app.js and nowhere else — if this parse breaks, a version
    # bump would silently vendor whatever the server happens to serve.
    libs = fetch_chart_libs.parse_chart_libs(
        TEMPLATE_APP_JS.read_text(encoding="utf-8")
    )
    globals_ = {lib["global"] for lib in libs}
    assert globals_ == {"echarts", "mermaid"}
    for lib in libs:
        assert lib["file"].endswith(".min.js")
        # A pin split across source lines must be rejoined, not truncated.
        assert lib["integrity"].startswith("sha384-")
        assert len(base64.b64decode(lib["integrity"].split("-", 1)[1])) == 48


@pytest.mark.unit
def test_vendors_pinned_bytes(tmp_path, monkeypatch):
    payload = b"window.echarts = {};"
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    (report_dir / "app.js").write_text(_app_js(payload), encoding="utf-8")
    monkeypatch.setattr(fetch_chart_libs, "fetch", lambda url: payload)

    results = fetch_chart_libs.vendor_chart_libs(report_dir=report_dir)
    assert results == [
        {"file": "echarts-5.6.1.min.js", "bytes": len(payload), "status": "downloaded"}
    ]
    vendored = report_dir / "report-assets" / "echarts-5.6.1.min.js"
    assert vendored.read_bytes() == payload

    # A second run must not re-download a copy that already matches the pin.
    def _explode(url):
        raise AssertionError(f"unexpected download: {url}")

    monkeypatch.setattr(fetch_chart_libs, "fetch", _explode)
    assert fetch_chart_libs.vendor_chart_libs(report_dir=report_dir)[0]["status"] == (
        "cached"
    )


@pytest.mark.unit
def test_refuses_to_write_a_mismatched_bundle(tmp_path, monkeypatch):
    # Vendoring a near-enough build would make local review a different test
    # from the deliverable, so a mismatch must fail rather than warn.
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    (report_dir / "app.js").write_text(_app_js(b"expected"), encoding="utf-8")
    monkeypatch.setattr(fetch_chart_libs, "fetch", lambda url: b"tampered")

    with pytest.raises(fetch_chart_libs.ChartLibError, match="integrity mismatch"):
        fetch_chart_libs.vendor_chart_libs(report_dir=report_dir)
    assert not (report_dir / "report-assets" / "echarts-5.6.1.min.js").exists()


@pytest.mark.unit
def test_pulls_from_the_requested_environment(tmp_path, monkeypatch):
    payload = b"window.echarts = {};"
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    (report_dir / "app.js").write_text(_app_js(payload), encoding="utf-8")
    seen: list[str] = []

    def _record(url):
        seen.append(url)
        return payload

    monkeypatch.setattr(fetch_chart_libs, "fetch", _record)
    fetch_chart_libs.vendor_chart_libs(report_dir=report_dir, subdomain="staging")
    assert seen == [
        "https://staging.zenable.app/report-assets/echarts-5.6.1.min.js"
    ]


@pytest.mark.unit
def test_rejects_app_js_without_chart_libs(tmp_path):
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    (report_dir / "app.js").write_text("// nothing here", encoding="utf-8")
    with pytest.raises(fetch_chart_libs.ChartLibError, match="does not declare"):
        fetch_chart_libs.vendor_chart_libs(report_dir=report_dir)
