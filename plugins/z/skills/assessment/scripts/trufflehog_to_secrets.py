# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Transform trufflehog NDJSON output into secrets.json (report evidence).

Replaces hand-typed secrets-scan numbers in a data.js "strength" with computed
counts straight from the generated TruffleHog output already on disk.

Usage:
    uv run --script trufflehog_to_secrets.py \\
        --secrets-dir <workspace/evidence/secrets> \\
        --out <secrets.json> \\
        [--note "..."] \\
        [--html <index.html-to-inline-into>] \\
        [--generated-at <ISO8601-or-empty>]

Auto-discovers ``trufflehog.*.json`` (NDJSON: one finding per line). The scan
label is derived from the filename infix — ``trufflehog.fs.json`` -> ``fs``,
``trufflehog.git.json`` -> ``git`` — and ``.analyzed`` siblings are ignored.

SECURITY: this payload is inlined into the published report, so it carries ONLY
trufflehog's ``Redacted`` value, never ``Raw``/``RawV2``. Emitting the live
secret would defeat the scan and leak it into a shared artifact.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _scan_label(path: Path) -> str:
    # trufflehog.<label>.json -> <label>
    m = re.match(r"trufflehog\.([A-Za-z0-9_-]+)\.json$", path.name)
    return m.group(1) if m else path.stem


def _location(record: dict) -> str:
    """Best-effort source location, redaction-safe (path/commit/line only)."""
    data = (record.get("SourceMetadata") or {}).get("Data") or {}
    for meta in data.values():
        if not isinstance(meta, dict):
            continue
        file = meta.get("file") or meta.get("path") or ""
        line = meta.get("line")
        commit = meta.get("commit")
        loc = file
        if line:
            loc = f"{loc}:{line}" if loc else f"line {line}"
        if commit:
            loc = f"{loc} @ {commit[:10]}" if loc else commit[:10]
        if loc:
            return loc
    return ""


def parse_trufflehog(path: Path) -> tuple[dict, list[dict]]:
    findings: list[dict] = []
    verified = 0
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # tolerate a trailing non-JSON summary line
        if not isinstance(rec, dict) or "DetectorName" not in rec:
            continue
        is_verified = bool(rec.get("Verified"))
        verified += int(is_verified)
        findings.append(
            {
                "scan": _scan_label(path),
                "detector": rec.get("DetectorName", ""),
                "detector_type": rec.get("DetectorType"),
                "verified": is_verified,
                "source": rec.get("SourceName", ""),
                "location": _location(rec),
                "redacted": rec.get("Redacted", ""),  # NEVER Raw / RawV2
            }
        )
    scan = {
        "scan": _scan_label(path),
        "output": path.name,
        "finding_count": len(findings),
        "verified_count": verified,
    }
    return scan, findings


def _discover(secrets_dir: Path) -> list[Path]:
    out = []
    for p in sorted(secrets_dir.glob("trufflehog.*.json")):
        if p.name.endswith(".analyzed.json") or ".analyzed" in p.name:
            continue
        out.append(p)
    return out


def build_payload(
    files: list[Path], note: str, generated_at: str | None = None
) -> dict:
    scans: list[dict] = []
    findings: list[dict] = []
    for p in files:
        scan, fs = parse_trufflehog(p)
        scans.append(scan)
        findings.extend(fs)

    detectors: dict[str, int] = {}
    for f in findings:
        detectors[f["detector"]] = detectors.get(f["detector"], 0) + 1
    verified = sum(1 for f in findings if f["verified"])

    ts = (
        generated_at
        if generated_at is not None
        else datetime.now(tz=timezone.utc).isoformat()
    )
    payload: dict = {
        "note": note,
        "scans": scans,
        "summary": {
            "total_findings": len(findings),
            "verified": verified,
            "unverified": len(findings) - verified,
            "detectors": dict(sorted(detectors.items())),
        },
        "findings": findings,
    }
    if ts:
        payload["generated_at"] = ts
    return payload


def _inline_into_html(html_path: Path, payload: dict) -> None:
    if not html_path.exists():
        print(
            f"WARN: --html {html_path} does not exist; skipping inline", file=sys.stderr
        )
        return
    html = html_path.read_text()
    inlined = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    new_block = f"<!-- SECRETS-BEGIN -->{inlined}<!-- SECRETS-END -->"
    patched, n = re.subn(
        r"<!--\s*SECRETS-BEGIN\s*-->.*?<!--\s*SECRETS-END\s*-->",
        lambda _m: new_block,
        html,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        print(
            "WARN: SECRETS markers not found in HTML — skipping inline", file=sys.stderr
        )
        return
    html_path.write_text(patched)
    print(f"Inlined secrets into {html_path}", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(description="trufflehog NDJSON -> secrets.json")
    p.add_argument("--secrets-dir", type=Path, help="dir of trufflehog.*.json")
    p.add_argument(
        "--file", type=Path, nargs="*", help="explicit trufflehog NDJSON files"
    )
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--note", default="")
    p.add_argument("--html", type=Path, default=None)
    p.add_argument(
        "--generated-at",
        default=None,
        metavar="ISO8601",
        help="fix the generated_at timestamp (empty string to omit for byte-deterministic output)",
    )
    args = p.parse_args()

    files = list(args.file or [])
    if args.secrets_dir:
        files += _discover(args.secrets_dir)
    if not files:
        print(
            "ERROR: no trufflehog JSON found (pass --secrets-dir or --file)",
            file=sys.stderr,
        )
        return 1

    payload = build_payload(files, args.note, args.generated_at)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    s = payload["summary"]
    print(
        f"Wrote {args.out}: {s['total_findings']} findings, {s['verified']} verified",
        file=sys.stderr,
    )
    if args.html is not None:
        _inline_into_html(args.html, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
