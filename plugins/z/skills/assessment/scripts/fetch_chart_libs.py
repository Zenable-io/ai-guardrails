# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Resolve, verify and vendor the chart libraries a report loads.

The report template carries NO version or hash of its own. It cannot know which
version the Zenable app currently serves, and a hand-copied pin that falls
behind fails as a browser-blocked script — a report that silently loses its
charts with nothing logged anywhere the authors would see.

So this script asks. It reads the public, unauthenticated version index the app
publishes, takes the version that app says is current, downloads those bytes,
checks them against the integrity the index declares, and then does two things:

1. Writes the resolved version + integrity into the report's `chart-libs-data`
   block. From that moment the report is pinned: it loads that exact versioned
   URL with that exact hash for the rest of its life, immutable and
   SRI-verified, exactly as before. What changed is only where the pin came
   from, and that it can no longer be stale.

2. Vendors the same bytes into `<report-dir>/report-assets/` for LOCAL review.
   A `file://` page has no origin to resolve the root-relative `/report-assets/`
   path against, and a `file://` response is opaque so SRI can never be
   satisfied there — the browser blocks the script outright rather than
   degrading. Without this, local review silently loses the risk matrix, the
   data-flow diagram and every repository-history chart, which is the part of
   the walkthrough that most needs eyes on it.

`app.js` reads the vendored copy only when the page is on `file://`, so a hosted
report is unaffected, and `build_report.py` emits only `report.html` from the
report directory, so the vendored copies never reach the deliverable.

No credentials are needed: both the index and the assets are public.

Usage:
    uv run --script fetch_chart_libs.py --report-dir <workspace>/report
    uv run --script fetch_chart_libs.py --report-dir <workspace>/report \\
        --subdomain staging
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# The versioned layout the app serves and that asset-retention tooling scans
# already-issued reports for. Enforced on whatever the index hands us so a
# malformed entry cannot produce a report whose asset version looks
# unreferenced and becomes eligible for removal.
ASSET_PATH_RE = re.compile(r"^report-assets/[A-Za-z0-9_]+-\d+\.\d+\.\d+\.min\.js$")
VERSIONS_DOC = "report-asset-versions.json"
# The globals app.js waits for. An asset the index offers that the report has no
# use for is ignored rather than downloaded.
WANTED = ("echarts", "mermaid")
TIMEOUT_SECONDS = 60


class ChartLibError(RuntimeError):
    """The chart libraries could not be resolved or vendored."""


def sri_digest(data: bytes, integrity: str) -> str:
    """Compute `data`'s digest in the algorithm `integrity` declares."""
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
        hint = ""
        if url.endswith(VERSIONS_DOC):
            # By far the likeliest cause, and not obvious from a bare 403/404:
            # the environment has not deployed a build that publishes the index.
            hint = (
                f"\nThe version index is missing from this environment. It is "
                f"published by the app, so an environment that has not yet "
                f"deployed a build containing it cannot serve it. Check "
                f"--subdomain (currently resolving {url}), or use an "
                f"environment that has it."
            )
        raise ChartLibError(f"download failed: {url} ({error}){hint}") from error


def resolve_libs(index: dict) -> list[dict[str, str]]:
    """Pick the current version of each wanted asset out of the published index.

    Everything the report will pin comes from here, so each entry is validated
    rather than trusted: a missing hash or an off-layout path becomes an error
    now, at authoring time, instead of a blocked script in a reader's browser.
    """
    assets = index.get("assets") or {}
    libs = []
    for name in WANTED:
        asset = assets.get(name)
        if not asset:
            raise ChartLibError(
                f"the app's {VERSIONS_DOC} does not offer {name!r}; the report "
                f"cannot render without it"
            )
        current = asset.get("current")
        entry = (asset.get("versions") or {}).get(current)
        if not current or not entry:
            raise ChartLibError(f"{name}: index names no usable current version")
        path, integrity = entry.get("path"), entry.get("integrity")
        if not integrity:
            raise ChartLibError(f"{name} {current}: index declares no integrity")
        if not ASSET_PATH_RE.match(path or ""):
            raise ChartLibError(
                f"{name} {current}: index path {path!r} is not the expected "
                f"report-assets/<name>-<semver>.min.js layout"
            )
        libs.append(
            {"global": name, "version": current, "path": path, "integrity": integrity}
        )
    return libs


CHART_LIBS_BLOCK_RE = re.compile(
    r"<!--\s*CHARTLIBS-BEGIN\s*-->(.*?)<!--\s*CHARTLIBS-END\s*-->", re.DOTALL
)


def existing_libs(html_path: Path) -> list[dict]:
    """What a previous run already pinned into this report, if anything."""
    if not html_path.is_file():
        return []
    match = CHART_LIBS_BLOCK_RE.search(html_path.read_text(encoding="utf-8"))
    if not match:
        return []
    raw = match.group(1).strip()
    if not raw or raw == "null":
        return []
    try:
        return (json.loads(raw) or {}).get("libs") or []
    except json.JSONDecodeError:
        return []


def usable_offline(libs: list[dict], target: Path) -> bool:
    """True when every already-pinned library is vendored and matches its hash.

    A report that has already been resolved needs nothing from the index: its
    pin is fixed for life and the bytes are on disk. Re-running the step should
    not turn a temporary outage into a failed assessment.
    """
    if not libs:
        return False
    for lib in libs:
        path, integrity = lib.get("path"), lib.get("integrity")
        if not path or not integrity:
            return False
        dest = target / path.rsplit("/", 1)[-1]
        if not dest.is_file() or sri_digest(dest.read_bytes(), integrity) != integrity:
            return False
    return True


def inline_into_html(html_path: Path, libs: list[dict]) -> None:
    """Pin the resolved libraries into the report's chart-libs-data block."""
    if not html_path.is_file():
        raise ChartLibError(f"missing {html_path}")
    payload = {"libs": [{k: lib[k] for k in ("global", "path", "integrity")} for lib in libs]}
    inlined = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    patched, count = re.subn(
        r"<!--\s*CHARTLIBS-BEGIN\s*-->.*?<!--\s*CHARTLIBS-END\s*-->",
        lambda _m: f"<!-- CHARTLIBS-BEGIN -->{inlined}<!-- CHARTLIBS-END -->",
        html_path.read_text(encoding="utf-8"),
        count=1,
        flags=re.DOTALL,
    )
    if not count:
        raise ChartLibError(f"CHARTLIBS markers not found in {html_path}")
    html_path.write_text(patched, encoding="utf-8")


def vendor_chart_libs(
    *, report_dir: Path, subdomain: str = "www", out_dir: Path | None = None
) -> list[dict[str, object]]:
    origin = f"https://{subdomain.strip() or 'www'}.zenable.app"
    target = out_dir or (report_dir / "report-assets")
    target.mkdir(parents=True, exist_ok=True)

    try:
        index = json.loads(fetch(f"{origin}/{VERSIONS_DOC}").decode("utf-8"))
    except ChartLibError:
        # A report that is already resolved is self-sufficient: its pin is fixed
        # for life and the bytes are on disk. Only a first resolve genuinely
        # needs the index, so don't let an outage fail an assessment that has
        # everything it needs already.
        already = existing_libs(report_dir / "index.html")
        if usable_offline(already, target):
            print(
                "warning: could not reach the version index; keeping the pin this "
                "report already carries (verified against the vendored bytes)",
                file=sys.stderr,
            )
            return [
                {
                    "file": lib["path"].rsplit("/", 1)[-1],
                    "bytes": (target / lib["path"].rsplit("/", 1)[-1]).stat().st_size,
                    "status": "kept",
                }
                for lib in already
            ]
        raise
    libs = resolve_libs(index)

    results: list[dict[str, object]] = []
    for lib in libs:
        name = lib["path"].rsplit("/", 1)[-1]
        dest = target / name
        pin = lib["integrity"]
        if dest.is_file() and sri_digest(dest.read_bytes(), pin) == pin:
            results.append(
                {"file": name, "bytes": dest.stat().st_size, "status": "cached"}
            )
            continue
        url = f"{origin}/{lib['path']}"
        payload = fetch(url)
        actual = sri_digest(payload, pin)
        if actual != pin:
            # The index and the bytes it points at disagree — the app is serving
            # something other than what it advertises. Vendoring anyway would
            # make local review pass against bytes the reader's browser will
            # block on SRI.
            raise ChartLibError(
                f"integrity mismatch for {url}\n"
                f"  index declares {pin}\n"
                f"  actual         {actual}"
            )
        dest.write_bytes(payload)
        results.append({"file": name, "bytes": len(payload), "status": "downloaded"})

    inline_into_html(report_dir / "index.html", libs)
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-dir",
        required=True,
        type=Path,
        help="the report workspace directory holding index.html",
    )
    parser.add_argument(
        "--subdomain",
        default="www",
        help="Zenable environment to resolve and download from (default: www)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="override the vendor destination (default: <report-dir>/report-assets)",
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
    print(f"Pinned chart libraries into {args.report_dir / 'index.html'}")
    print(f"Vendored copies for local review in {target}")
    for result in results:
        print(f"  {result['file']:<28} {result['bytes']:>10,} bytes  {result['status']}")
    print("The vendored copies are local-only and are not packaged into the bundle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
