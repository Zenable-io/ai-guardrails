# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Vendor the pinned echarts/mermaid bundles next to a report for LOCAL viewing.

The hosted report always loads the chart libraries from the Zenable app's
`/report-assets/`, with the browser enforcing the SRI pins in `app.js`. A report
opened from `file://` has no origin to resolve that root-relative path against,
and a `file://` response is opaque so SRI can never be satisfied there — the
browser blocks the script outright rather than falling back. The result is a
local review with no risk matrix and no data-flow diagram.

This script closes that gap: it downloads the SAME version-pinned files, checks
their bytes against the SAME sha384 pins `app.js` uses, and writes them to
`<report-dir>/report-assets/`. `app.js` reads that directory only when the page
is on `file://`, so a hosted report is unaffected and the pin is still enforced
— just here, at vendor time, instead of in the browser at load time.

The pins are parsed out of `app.js` rather than restated, so there is exactly
one place to bump a chart library version.

`build_report.py` emits only `report.html` from the report directory, so the
vendored copies are never packaged into the deliverable bundle.

Usage:
    uv run --script fetch_chart_libs.py --report-dir <workspace>/report
    uv run --script fetch_chart_libs.py --report-dir <workspace>/report \\
        --subdomain staging
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

CHART_LIBS_RE = re.compile(
    r"""\{\s*global:\s*["'](?P<global>[^"']+)["']\s*,\s*"""
    r"""file:\s*["'](?P<file>[^"']+)["']\s*,\s*"""
    r"""integrity:\s*(?P<integrity>(?:\s*["'][^"']*["']\s*\+?)+)""",
    re.VERBOSE,
)
_STRING_RE = re.compile(r"""["']([^"']*)["']""")
TIMEOUT_SECONDS = 60


class ChartLibError(RuntimeError):
    """A pinned chart library could not be vendored."""


def parse_chart_libs(app_js_text: str) -> list[dict[str, str]]:
    """Read the CHART_LIBS pins straight out of app.js."""
    start = app_js_text.find("const CHART_LIBS")
    if start == -1:
        raise ChartLibError("app.js does not declare CHART_LIBS")
    end = app_js_text.find("];", start)
    if end == -1:
        raise ChartLibError("app.js CHART_LIBS declaration is unterminated")
    block = app_js_text[start:end]
    libs = [
        {
            "global": match.group("global"),
            "file": match.group("file"),
            # app.js wraps long sha384 pins across lines as concatenated
            # string literals; rejoin them before comparing.
            "integrity": "".join(_STRING_RE.findall(match.group("integrity"))),
        }
        for match in CHART_LIBS_RE.finditer(block)
    ]
    if not libs:
        raise ChartLibError("app.js CHART_LIBS is empty or unparseable")
    return libs


def sri_digest(data: bytes, integrity: str) -> str:
    """Compute `data`'s digest in the same algorithm `integrity` declares."""
    algo, _, _ = integrity.partition("-")
    if algo not in {"sha256", "sha384", "sha512"}:
        raise ChartLibError(f"unsupported SRI algorithm: {integrity!r}")
    digest = hashlib.new(algo, data).digest()
    return f"{algo}-{base64.b64encode(digest).decode('ascii')}"


def fetch(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            return response.read()
    except urllib.error.URLError as error:
        raise ChartLibError(f"download failed: {url} ({error})") from error


def vendor_chart_libs(
    *, report_dir: Path, subdomain: str = "www", out_dir: Path | None = None
) -> list[dict[str, object]]:
    app_js = report_dir / "app.js"
    if not app_js.is_file():
        raise ChartLibError(f"missing {app_js}")
    libs = parse_chart_libs(app_js.read_text(encoding="utf-8"))
    target = out_dir or (report_dir / "report-assets")
    target.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    base = f"https://{subdomain.strip() or 'www'}.zenable.app/report-assets"
    for lib in libs:
        dest = target / lib["file"]
        pin = lib["integrity"]
        if dest.is_file() and sri_digest(dest.read_bytes(), pin) == pin:
            results.append(
                {"file": lib["file"], "bytes": dest.stat().st_size, "status": "cached"}
            )
            continue
        url = f"{base}/{lib['file']}"
        payload = fetch(url)
        actual = sri_digest(payload, pin)
        if actual != pin:
            # Refuse to write a mismatched bundle. The whole point of vendoring
            # is that the local copy is byte-identical to what the hosted report
            # serves; a near-enough build would make local review a different
            # test from the deliverable.
            raise ChartLibError(
                f"integrity mismatch for {url}\n"
                f"  expected {pin}\n"
                f"  actual   {actual}"
            )
        dest.write_bytes(payload)
        results.append(
            {"file": lib["file"], "bytes": len(payload), "status": "downloaded"}
        )
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-dir",
        required=True,
        type=Path,
        help="The report workspace directory holding app.js.",
    )
    parser.add_argument(
        "--subdomain",
        default="www",
        help="Zenable environment to pull the pinned assets from (default: www).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Override the destination (default: <report-dir>/report-assets).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        results = vendor_chart_libs(
            report_dir=args.report_dir,
            subdomain=args.subdomain,
            out_dir=args.out_dir,
        )
    except ChartLibError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    target = args.out_dir or (args.report_dir / "report-assets")
    print(f"Vendored chart libraries into {target}")
    for result in results:
        print(f"  {result['file']:<28} {result['bytes']:>10,} bytes  {result['status']}")
    print("These are for LOCAL viewing only and are not packaged into the bundle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
