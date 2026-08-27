# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Transform syft/grype SBOM outputs into dependencies.json (report Appendix D).

Replaces the hand-transcribed `dependencies.*` block in data.js. A hand-counted
component or license total drifts the moment the tree changes, so every number
here is computed from the generated Syft/Grype output already on disk.

Usage:
    uv run --script sbom_to_dependencies.py \\
        --sbom-dir <workspace/evidence/sbom> \\
        --out <dependencies.json> \\
        [--license-resolution <licenses.json>] \\
        [--note "..."] \\
        [--html <index.html-to-inline-into>]

Auto-discovers every ``*.syft.json`` (component + license inventory) and
``*.grype.json`` (vulnerabilities) under ``--sbom-dir``, skipping the
``.cdx.json`` / ``.spdx.json`` re-encodings (same data, different schema). Pass
explicit ``--syft`` / ``--grype`` files to override discovery.

Provenance deliberately records only what the output proves — tool, version
(from each file's ``descriptor``), scan target (``source``), the output filename,
and the computed result. The invoking CLI command is NOT stored in syft/grype
output, so it is omitted rather than re-typed (re-typing is exactly the drift
this script removes).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _source_target(doc: dict) -> str:
    src = doc.get("source", {}) or {}
    # syft uses target (str for dir/file, dict for image); grype mirrors it.
    target = src.get("target")
    if isinstance(target, str):
        return target
    if isinstance(target, dict):
        return target.get("userInput") or target.get("path") or src.get("name", "")
    return src.get("name", "") or src.get("type", "")


def _descriptor(doc: dict) -> tuple[str, str]:
    d = doc.get("descriptor", {}) or {}
    return d.get("name", "?"), d.get("version", "?")


def _licenses_of(artifact: dict) -> list[str]:
    out: list[str] = []
    for lic in artifact.get("licenses", []) or []:
        spdx = lic.get("spdxExpression") or lic.get("value")
        if spdx and spdx not in out:
            out.append(spdx)
    return out


def parse_syft(path: Path) -> tuple[dict, list[dict]]:
    doc = json.loads(path.read_text())
    tool, version = _descriptor(doc)
    target = _source_target(doc)
    components = []
    for a in doc.get("artifacts", []) or []:
        components.append(
            {
                "name": a.get("name", ""),
                "version": a.get("version", ""),
                "type": a.get("type", ""),
                "language": a.get("language", "") or None,
                "licenses": _licenses_of(a),
                "resolved_license": None,  # populated by resolve_licenses.py post-pass
                "license_source": None,  # POM or file the resolved license came from
                "purl": a.get("purl", "") or None,
                "target": target,
            }
        )
    scan = {
        "tool": tool,
        "version": version,
        "target": target,
        "output": path.name,
        "result": f"{len(components)} component(s) inventoried",
    }
    return scan, components


def parse_grype(path: Path) -> tuple[dict, list[dict]]:
    doc = json.loads(path.read_text())
    tool, version = _descriptor(doc)
    target = _source_target(doc)
    vulns = []
    for m in doc.get("matches", []) or []:
        v = m.get("vulnerability", {}) or {}
        art = m.get("artifact", {}) or {}
        fix = v.get("fix", {}) or {}
        vulns.append(
            {
                "id": v.get("id", ""),
                "severity": v.get("severity", ""),
                "package": art.get("name", ""),
                "version": art.get("version", ""),
                "fixed_in": ", ".join(fix.get("versions", []) or []) or None,
                "fix_state": fix.get("state", "") or None,
                "data_source": v.get("dataSource", "") or None,
                "target": target,
            }
        )
    if vulns:
        sev = {}
        for x in vulns:
            sev[x["severity"]] = sev.get(x["severity"], 0) + 1
        sev_str = ", ".join(f"{n} {s}" for s, n in sorted(sev.items()))
        result = f"{len(vulns)} finding(s) — {sev_str}"
    else:
        result = "No vulnerabilities found"
    scan = {
        "tool": tool,
        "version": version,
        "target": target,
        "output": path.name,
        "result": result,
    }
    return scan, vulns


def _dedupe_components(rows: list[dict]) -> list[dict]:
    """Union by (name, version, type); merge the `target` of each occurrence so
    a component appearing in multiple scans (e.g. shipped jar + source tree)
    lists every target it was seen in."""
    merged: dict[tuple, dict] = {}
    for r in rows:
        key = (r["name"], r["version"], r["type"])
        if key in merged:
            tgt = r.get("target")
            if tgt and tgt not in merged[key]["targets"]:
                merged[key]["targets"].append(tgt)
            for lic in r["licenses"]:
                if lic not in merged[key]["licenses"]:
                    merged[key]["licenses"].append(lic)
        else:
            row = {k: v for k, v in r.items() if k != "target"}
            row["targets"] = [r["target"]] if r.get("target") else []
            merged[key] = row
    return sorted(merged.values(), key=lambda r: (r["name"].lower(), r["version"]))


def _license_counts(components: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for c in components:
        licenses = (
            c.get("verified_licenses") or c.get("licenses") or ["(none detected)"]
        )
        for lic in licenses:
            counts[lic] = counts.get(lic, 0) + 1
    return [
        {"license": lic, "count": n}
        for lic, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _discover(sbom_dir: Path, kind: str) -> list[Path]:
    # `kind` = "syft" | "grype". Skip the .cdx.json / .spdx.json re-encodings.
    out = []
    for p in sorted(sbom_dir.glob(f"*.{kind}.json")):
        if p.name.endswith((".cdx.json", ".spdx.json")):
            continue
        out.append(p)
    return out


def _load_license_resolutions(path: Path | None) -> dict[tuple[str, str], dict]:
    if path is None:
        return {}
    doc = json.loads(path.read_text())
    out: dict[tuple[str, str], dict] = {}
    for item in doc.get("items", []) or []:
        if item.get("type") != "license":
            continue
        data = item.get("data", {}) or {}
        component = data.get("component")
        version = data.get("version")
        if not component or not version:
            continue
        provenance = item.get("provenance", {}) or {}
        out[(component, version)] = {
            "verified_licenses": data.get("verified", []) or [],
            "resolved_licenses": data.get("resolved", []) or [],
            "license_source": provenance.get("sourcePomRel") or data.get("via") or None,
        }
    return out


def _apply_license_resolutions(
    components: list[dict],
    resolutions: dict[tuple[str, str], dict],
) -> None:
    for component in components:
        resolution = resolutions.get((component["name"], component["version"]))
        if not resolution:
            continue
        component["detected_licenses"] = list(component.get("licenses") or [])
        component["verified_licenses"] = list(resolution["verified_licenses"])
        component["resolved_licenses"] = list(resolution["resolved_licenses"])
        component["license_source"] = resolution["license_source"]


def build_payload(
    syft_files: list[Path],
    grype_files: list[Path],
    note: str,
    generated_at: str | None = None,
    license_resolution: Path | None = None,
) -> dict:
    scans: list[dict] = []
    components: list[dict] = []
    vulns: list[dict] = []
    for p in syft_files:
        scan, comps = parse_syft(p)
        scans.append(scan)
        components.extend(comps)
    for p in grype_files:
        scan, vs = parse_grype(p)
        scans.append(scan)
        vulns.extend(vs)

    components = _dedupe_components(components)
    _apply_license_resolutions(
        components,
        _load_license_resolutions(license_resolution),
    )
    # Dedupe vulnerabilities by (id, package, version) across scan modes.
    seen: set = set()
    uniq_vulns = []
    for v in vulns:
        key = (v["id"], v["package"], v["version"])
        if key not in seen:
            seen.add(key)
            uniq_vulns.append(v)
    licenses = _license_counts(components)

    ts = (
        generated_at
        if generated_at is not None
        else datetime.now(tz=timezone.utc).isoformat()
    )
    payload: dict = {
        "note": note,
        "scans": scans,
        "components": components,
        "licenses": licenses,
        "vulnerabilities": uniq_vulns,
        "summary": {
            "component_count": len(components),
            "license_count": len(
                [lc for lc in licenses if lc["license"] != "(none detected)"]
            ),
            "vulnerability_count": len(uniq_vulns),
        },
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
    new_block = f"<!-- DEPENDENCIES-BEGIN -->{inlined}<!-- DEPENDENCIES-END -->"
    patched, n = re.subn(
        r"<!--\s*DEPENDENCIES-BEGIN\s*-->.*?<!--\s*DEPENDENCIES-END\s*-->",
        lambda _m: new_block,
        html,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        print(
            "WARN: DEPENDENCIES markers not found in HTML — skipping inline",
            file=sys.stderr,
        )
        return
    html_path.write_text(patched)
    print(f"Inlined dependencies into {html_path}", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(description="syft/grype SBOM -> dependencies.json")
    p.add_argument("--sbom-dir", type=Path, help="dir of *.syft.json / *.grype.json")
    p.add_argument("--syft", type=Path, nargs="*", help="explicit syft json files")
    p.add_argument("--grype", type=Path, nargs="*", help="explicit grype json files")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument(
        "--license-resolution",
        type=Path,
        default=None,
        help="optional generated licenses.json from resolve_licenses.py",
    )
    p.add_argument("--note", default="", help="provenance note for Appendix D")
    p.add_argument("--html", type=Path, default=None)
    p.add_argument(
        "--generated-at",
        default=None,
        metavar="ISO8601",
        help="fix the generated_at timestamp (empty string to omit for byte-deterministic output)",
    )
    args = p.parse_args()

    syft_files = list(args.syft or [])
    grype_files = list(args.grype or [])
    if args.sbom_dir:
        syft_files += _discover(args.sbom_dir, "syft")
        grype_files += _discover(args.sbom_dir, "grype")
    if not syft_files and not grype_files:
        print(
            "ERROR: no syft/grype JSON found (pass --sbom-dir or --syft/--grype)",
            file=sys.stderr,
        )
        return 1

    payload = build_payload(
        syft_files,
        grype_files,
        args.note,
        args.generated_at,
        args.license_resolution,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(
        f"Wrote {args.out}: {payload['summary']['component_count']} components, "
        f"{payload['summary']['vulnerability_count']} vulns",
        file=sys.stderr,
    )
    if args.html is not None:
        _inline_into_html(args.html, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
