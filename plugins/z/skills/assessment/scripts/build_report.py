#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Build an uploadable Zenable report bundle ZIP from a report workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import unicodedata
import zipfile
from pathlib import Path

REPORT_ID_PLACEHOLDER = "__REPORT_ID__"
PREVIEW_MAX = 280
ZIP_DATE = (1980, 1, 1, 0, 0, 0)
_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    '"': '"',
    "'": "'",
    "\\": "\\",
    "/": "/",
    "`": "`",
}


def _decode_js_string(text: str, i: int) -> tuple[str, int]:
    quote = text[i]
    i += 1
    out: list[str] = []
    while i < len(text):
        c = text[i]
        if c == "\\":
            if i + 1 >= len(text):
                raise ValueError("unterminated JS escape sequence")
            nxt = text[i + 1]
            if nxt == "u":
                if i + 6 > len(text):
                    raise ValueError("unterminated JS unicode escape")
                hex_digits = text[i + 2 : i + 6]
                try:
                    out.append(chr(int(hex_digits, 16)))
                except ValueError as e:
                    raise ValueError(
                        f"invalid JS unicode escape: {hex_digits!r}"
                    ) from e
                i += 6
                continue
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
            continue
        if c == quote:
            return "".join(out), i + 1
        out.append(c)
        i += 1
    raise ValueError("unterminated JS string literal")


def _read_concat_string(text: str, i: int) -> str:
    parts: list[str] = []
    while i < len(text):
        while i < len(text) and text[i] in " \t\r\n":
            i += 1
        if i >= len(text) or text[i] not in "\"'`":
            break
        val, i = _decode_js_string(text, i)
        parts.append(val)
        j = i
        while j < len(text) and text[j] in " \t\r\n":
            j += 1
        if j < len(text) and text[j] == "+":
            i = j + 1
            continue
        break
    return "".join(parts)


def _block(text: str, key: str) -> str:
    match = re.search(r"\b" + re.escape(key) + r"\s*:\s*\{", text)
    if not match:
        raise KeyError(key)
    start = match.end() - 1
    depth = 0
    in_str = None
    i = start
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
        elif c in "\"'`":
            in_str = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1
    raise ValueError(f"unbalanced braces for {key}")


def _scalar(text: str, key: str, default: str = "") -> str:
    match = re.search(r"\b" + re.escape(key) + r"\s*:\s*", text)
    if not match:
        return default
    return _read_concat_string(text, match.end())


def _first_array_string(text: str, key: str) -> str:
    match = re.search(r"\b" + re.escape(key) + r"\s*:\s*\[", text)
    if not match:
        return ""
    return _read_concat_string(text, match.end())


def _slugify_report_hint(value: str) -> str:
    raw = str(value or "").strip()
    ascii_text = (
        unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    )
    base = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-").lower()
    if not base:
        base = "report"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    max_base_len = 128 - len(digest) - 1
    return f"{(base[:max_base_len].rstrip('-') or 'report')}-{digest}"


def _meta_severity_key(severity: str) -> str:
    key = str(severity or "").strip().lower()
    if key in {"crit", "critical", "blocker"}:
        return "critical"
    if key in {"hi", "high", "error", "severe"}:
        return "high"
    if key in {"medium", "moderate", "med", "warning", "warn"}:
        return "medium"
    if key in {"low", "info", "informational", "note"}:
        return "low"
    return key


def derive_meta(data_js_text: str) -> dict[str, object]:
    meta_block = _block(data_js_text, "meta")
    try:
        risk_block = _block(data_js_text, "overallRisk")
        risk = _scalar(risk_block, "level")
    except KeyError:
        risk = ""

    severities = re.findall(r'\bseverity\s*:\s*"([A-Za-z]+)"', data_js_text)
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for severity in severities:
        key = _meta_severity_key(severity)
        if key in counts:
            counts[key] += 1

    preview = re.sub(
        r"\s+", " ", _first_array_string(data_js_text, "takeaways")
    ).strip()
    if len(preview) > PREVIEW_MAX:
        preview = preview[: PREVIEW_MAX - 1].rsplit(" ", 1)[0].rstrip() + "..."

    client = _scalar(meta_block, "client")
    target = _scalar(meta_block, "target")
    engagement = _scalar(meta_block, "engagement")
    report_date = _scalar(meta_block, "date")
    report_slug = _scalar(meta_block, "reportSlug") or _slugify_report_hint(
        " ".join(part for part in (target, client, engagement, report_date) if part)
    )

    return {
        "report_id": _scalar(meta_block, "reportId", REPORT_ID_PLACEHOLDER),
        "report_slug": report_slug,
        "client": client,
        "target": target,
        "engagement": engagement,
        "report_date": report_date,
        "classification": _scalar(meta_block, "classification"),
        "overall_risk_level": risk,
        "findings_total": len(severities),
        "severity_counts": counts,
        "preview": preview,
    }


def _script_safe(js: str) -> str:
    return re.sub(r"</(script)", r"<\/\1", js, flags=re.IGNORECASE)


def _style_safe(css: str) -> str:
    return re.sub(r"</(style)", r"<\/\1", css, flags=re.IGNORECASE)


def _replace_once(pattern: str, repl: str, html: str, label: str) -> str:
    html, count = re.subn(pattern, repl, html, count=1, flags=re.IGNORECASE)
    if count != 1:
        raise RuntimeError(f"expected {label} tag in index.html")
    return html


def _validate_resource_tags(html: str) -> None:
    # NOTHING external may remain as a static tag — not even /report-assets/.
    # A static classic <script src> blocks the HTML parser, so a middlebox
    # that never answers would wedge the report before it hydrates; the chart
    # libraries are loaded dynamically by app.js (CHART_LIBS) instead.
    bad: list[str] = []
    tag_re = re.compile(
        r"<(?:link|script|img|iframe|source|audio|video)\b[^>]*(?:src|href)=[\"']([^\"']+)[\"'][^>]*>",
        re.IGNORECASE,
    )
    for match in tag_re.finditer(html):
        value = match.group(1)
        if value.startswith("#"):
            continue
        bad.append(match.group(0))
    if bad:
        raise RuntimeError(f"report.html still references external resources: {bad!r}")


def build_report_html(report_dir: Path, asset_subdomain: str = "") -> str:
    index_html = report_dir / "index.html"
    styles_css = report_dir / "styles.css"
    data_js = report_dir / "data.js"
    app_js = report_dir / "app.js"
    for required in (index_html, styles_css, data_js, app_js):
        if not required.is_file():
            raise RuntimeError(f"missing required report input: {required}")

    html = index_html.read_text(encoding="utf-8")
    html = re.sub(
        r"[ \t]*<link\b[^>]*href=[\"']https?://[^\"']+[\"'][^>]*>\s*\n?",
        "",
        html,
        flags=re.IGNORECASE,
    )

    tokens = {
        "css": "\x01INLINE_CSS\x01",
        "data": "\x01INLINE_DATA\x01",
        "app": "\x01INLINE_APP\x01",
    }
    html = _replace_once(
        r"<link\b(?=[^>]*rel=[\"']stylesheet[\"'])(?=[^>]*href=[\"']styles\.css[\"'])[^>]*>",
        tokens["css"],
        html,
        "styles.css",
    )
    html = _replace_once(
        r"<script\b[^>]*src=[\"']data\.js[\"'][^>]*>\s*</script>",
        tokens["data"],
        html,
        "data.js",
    )
    html = _replace_once(
        r"<script\b[^>]*src=[\"']app\.js[\"'][^>]*>\s*</script>",
        tokens["app"],
        html,
        "app.js",
    )
    _validate_resource_tags(html)

    html = html.replace(
        tokens["css"],
        f"<style>\n{_style_safe(styles_css.read_text(encoding='utf-8'))}\n</style>",
        1,
    )
    html = html.replace(
        tokens["data"],
        f"<script>\n{_script_safe(data_js.read_text(encoding='utf-8'))}\n</script>",
        1,
    )
    # When --asset-subdomain is passed, stamp it so a LOCALLY-opened report
    # knows which Zenable environment to pull the version-pinned
    # /report-assets/ chart libs from. Unstamped reports default to "www" in
    # app.js, which is what a customer deliverable wants. Deliberately an
    # explicit flag and NOT the ambient ZENABLE_SUBDOMAIN env var: inheriting
    # that would silently stamp a deliverable with whatever environment the
    # shell that built it happened to point at.
    sub = asset_subdomain.strip()
    subdomain_script = (
        f"<script>window.__ZENABLE_SUBDOMAIN__ = {json.dumps(sub)};</script>\n"
        if sub
        else ""
    )
    html = html.replace(
        tokens["app"],
        f"{subdomain_script}<script>\n{_script_safe(app_js.read_text(encoding='utf-8'))}\n</script>",
        1,
    )
    return html


def _ignore_generated(_dir: str, names: list[str]) -> list[str]:
    return [name for name in names if name == "__pycache__" or name.endswith(".pyc")]


def copy_tree(src: Path, dst: Path) -> int:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return 0
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_ignore_generated)
    return sum(1 for path in dst.rglob("*") if path.is_file())


def write_zip(out_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in out_dir.rglob("*") if p.is_file()):
            if path.resolve() == zip_path.resolve():
                continue
            rel = path.relative_to(out_dir).as_posix()
            info = zipfile.ZipInfo(rel, ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def build_bundle(
    *,
    report_dir: Path,
    context_dir: Path,
    evidence_dir: Path,
    experiments_dir: Path,
    out_dir: Path,
    zip_out: Path,
    asset_subdomain: str = "",
) -> dict[str, object]:
    data_js_text = (report_dir / "data.js").read_text(encoding="utf-8")
    meta = derive_meta(data_js_text)
    report_html = build_report_html(report_dir, asset_subdomain=asset_subdomain)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "report.html").write_text(report_html, encoding="utf-8")
    (out_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    context_count = copy_tree(context_dir, out_dir / "context")
    evidence_count = copy_tree(evidence_dir, out_dir / "evidence")
    experiment_count = copy_tree(experiments_dir, out_dir / "experiments")
    write_zip(out_dir, zip_out)
    return {
        "meta": meta,
        "report_bytes": (out_dir / "report.html").stat().st_size,
        "context_count": context_count,
        "evidence_count": evidence_count,
        "experiment_count": experiment_count,
        "zip_path": str(zip_out),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--context-dir", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--experiments-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--zip-out", type=Path)
    parser.add_argument(
        "--asset-subdomain",
        default="",
        help=(
            "Stamp window.__ZENABLE_SUBDOMAIN__ so a locally-opened report pulls "
            "/report-assets/ chart libs from <sub>.zenable.app instead of the "
            "www default. Omit for customer deliverables. Never inherited from "
            "the environment."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    zip_out = args.zip_out or args.out_dir / "assessment-bundle.zip"
    result = build_bundle(
        report_dir=args.report_dir,
        context_dir=args.context_dir,
        evidence_dir=args.evidence_dir,
        experiments_dir=args.experiments_dir,
        out_dir=args.out_dir,
        zip_out=zip_out,
        asset_subdomain=args.asset_subdomain,
    )
    meta = result["meta"]
    print(f"Wrote bundle dir: {args.out_dir}")
    print(f"Wrote bundle zip: {zip_out}")
    print(f"  report.html   {result['report_bytes']:,} bytes")
    print(
        "  meta.json     report_id={report_id} risk={overall_risk_level} findings={findings_total}".format(
            **meta
        )
    )
    print(f"  context/     {result['context_count']} file(s)")
    print(f"  evidence/     {result['evidence_count']} file(s)")
    print(f"  experiments/  {result['experiment_count']} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
