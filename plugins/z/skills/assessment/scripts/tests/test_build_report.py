import json
import zipfile
from pathlib import Path

import pytest
from conftest import load_script

build_report = load_script("build_report")


def _write_report(report_dir: Path, *, extra_resource: str = "") -> None:
    report_dir.mkdir()
    (report_dir / "index.html").write_text(
        f"""<!doctype html>
<html>
<head>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Raleway">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main>Report</main>
  {extra_resource}
  <script src="data.js"></script>
  <script src="app.js"></script>
</body>
</html>
""",
        encoding="utf-8",
    )
    (report_dir / "styles.css").write_text("body { color: #111; }", encoding="utf-8")
    (report_dir / "data.js").write_text(
        """window.REPORT = {
  meta: {
    client: "Acme",
    engagement: "Code Scan",
    target: "service",
    date: "2026-06-26",
    classification: "Confidential",
    reportId: "__REPORT_ID__"
  },
  takeaways: ["One concise takeaway."],
  overallRisk: { level: "High" },
  findings: [{ severity: "High" }, { severity: "Low" }]
};""",
        encoding="utf-8",
    )
    (report_dir / "app.js").write_text("window.__appLoaded = true;", encoding="utf-8")


@pytest.mark.unit
def test_build_report_writes_bundle_dir_and_zip(tmp_path):
    report_dir = tmp_path / "report"
    context_dir = tmp_path / "context"
    evidence_dir = tmp_path / "evidence"
    experiments_dir = tmp_path / "experiments"
    out_dir = tmp_path / "dist"
    _write_report(report_dir)
    context_dir.mkdir()
    (context_dir / "logan-email.md").write_text("verbatim", encoding="utf-8")
    evidence_dir.mkdir()
    (evidence_dir / "artifacts.json").write_text("{}", encoding="utf-8")
    experiments_dir.mkdir()
    (experiments_dir / "run.out").write_text("ok", encoding="utf-8")

    assert (
        build_report.main(
            [
                "--report-dir",
                str(report_dir),
                "--context-dir",
                str(context_dir),
                "--evidence-dir",
                str(evidence_dir),
                "--experiments-dir",
                str(experiments_dir),
                "--out-dir",
                str(out_dir),
            ]
        )
        == 0
    )
    zip_out = out_dir / "assessment-bundle.zip"
    assert zip_out.is_file()

    html = (out_dir / "report.html").read_text(encoding="utf-8")
    assert "styles.css" not in html
    assert "data.js" not in html
    assert "app.js" not in html
    assert "fonts.googleapis.com" not in html
    # Chart libs are loaded dynamically by app.js; no static tags survive, and
    # no environment subdomain is stamped unless explicitly requested.
    assert "<script src=" not in html
    assert "__ZENABLE_SUBDOMAIN__" not in html

    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["report_id"] == "__REPORT_ID__"
    assert meta["report_slug"] == "service-acme-code-scan-2026-06-26-9fe66f74"
    assert meta["client"] == "Acme"
    assert meta["findings_total"] == 2
    assert meta["severity_counts"] == {
        "critical": 0,
        "high": 1,
        "medium": 0,
        "low": 1,
    }

    with zipfile.ZipFile(zip_out) as archive:
        assert set(archive.namelist()) == {
            "context/logan-email.md",
            "evidence/artifacts.json",
            "experiments/run.out",
            "meta.json",
            "report.html",
        }


@pytest.mark.unit
def test_build_report_normalizes_finding_severity_counts(tmp_path):
    report_dir = tmp_path / "report"
    _write_report(report_dir)
    data_js = report_dir / "data.js"
    data_js.write_text(
        """window.REPORT = {
  meta: {
    client: "Acme",
    engagement: "Code Scan",
    target: "service",
    date: "2026-06-26",
    classification: "Confidential",
    reportId: "__REPORT_ID__"
  },
  takeaways: ["One concise takeaway."],
  overallRisk: { level: "High" },
  findings: [
    { severity: "critical" },
    { severity: "ERROR" },
    { severity: "Moderate" },
    { severity: "warn" },
    { severity: "Info" }
  ]
};""",
        encoding="utf-8",
    )

    meta = build_report.derive_meta(data_js.read_text(encoding="utf-8"))

    assert meta["findings_total"] == 5
    assert meta["severity_counts"] == {
        "critical": 1,
        "high": 1,
        "medium": 2,
        "low": 1,
    }


@pytest.mark.unit
def test_build_report_rejects_unbundled_resources(tmp_path):
    report_dir = tmp_path / "report"
    _write_report(report_dir, extra_resource='<img src="logo.png">')
    with pytest.raises(RuntimeError, match="external resources"):
        build_report.build_report_html(report_dir)


@pytest.mark.unit
def test_build_report_rejects_static_report_asset_tags(tmp_path):
    # Chart libs must load dynamically (app.js CHART_LIBS): a static classic
    # <script src> blocks the HTML parser, so a stalled network middlebox
    # would wedge the report before it hydrates.
    report_dir = tmp_path / "report"
    _write_report(
        report_dir,
        extra_resource='<script src="/report-assets/echarts-5.6.1.min.js"></script>',
    )
    with pytest.raises(RuntimeError, match="external resources"):
        build_report.build_report_html(report_dir)


@pytest.mark.unit
def test_build_report_stamps_explicit_asset_subdomain_only(tmp_path, monkeypatch):
    # An ambient ZENABLE_SUBDOMAIN must never leak into a bundle; only the
    # explicit flag stamps the fallback origin.
    monkeypatch.setenv("ZENABLE_SUBDOMAIN", "ambient")
    report_dir = tmp_path / "report"
    _write_report(report_dir)

    html = build_report.build_report_html(report_dir)
    assert "__ZENABLE_SUBDOMAIN__" not in html

    stamped = build_report.build_report_html(report_dir, asset_subdomain="staging")
    assert '<script>window.__ZENABLE_SUBDOMAIN__ = "staging";</script>' in stamped


@pytest.mark.unit
def test_decode_js_string_rejects_trailing_escape():
    with pytest.raises(ValueError, match="unterminated JS escape"):
        build_report._decode_js_string('"abc\\', 0)


@pytest.mark.unit
def test_decode_js_string_rejects_short_unicode_escape():
    with pytest.raises(ValueError, match="unterminated JS unicode escape"):
        build_report._decode_js_string('"abc\\u12"', 0)


@pytest.mark.unit
def test_decode_js_string_rejects_invalid_unicode_escape():
    with pytest.raises(ValueError, match="invalid JS unicode escape"):
        build_report._decode_js_string('"abc\\uZZZZ"', 0)
