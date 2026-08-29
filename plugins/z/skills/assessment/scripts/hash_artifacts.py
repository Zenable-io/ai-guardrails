# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Hash the artifacts provided for review into artifacts.json (report Appendix A).

Replaces the hand-transcribed `providedArtifacts.items` in data.js with a
generated, reproducible evidence file. A hand-typed hash silently fingerprints
the wrong build or a stale commit, so every hash here is computed from the tree.

Usage:
    uv run --script hash_artifacts.py \\
        --repo-root <path-to-target-repo> \\
        --spec <path-to-artifacts-spec.json> \\
        --out <path-to-artifacts.json> \\
        [--commit <sha>] \\
        [--html <path-to-index.html-to-inline-into>]

The spec is a JSON object describing what to hash, so the same script serves any
engagement:

    {
      "note": "Hashes fingerprint the artifacts AS PROVIDED ...",
      "items": [
        { "name": "src tree (excludes build output, workspace, .git/)",
          "kind": "source", "mode": "tree", "path": ".",
          "exclude": ["target", "zenable-assessment", ".git"] },
        { "name": ".git (filtered)", "kind": "vcs", "mode": "tree", "path": ".git" },
        { "name": "dist/app.jar", "kind": "binary", "mode": "file",
          "path": "dist/app.jar" }
      ]
    }

`mode`:
  - `file` — plain SHA-256 of the file bytes.
  - `tree` — a deterministic tree-hash over every regular file under `path`:
    each file contributes `<repo-relative-path>\\0<sha256-hex>\\0`, concatenated
    in sorted path order and SHA-256'd. Stable across machines; drifts only when
    the tree's content or layout changes.

When `--commit` is given, file bytes and tree membership are read from that commit
via git (reproducible regardless of working-tree state) instead of the working
tree. A `file` artifact missing at that commit (e.g. an out-of-band binary that
was never committed) is hashed from the working tree and flagged
`reproducible: false` so the report can say so.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT: Path = Path.cwd()


def _run_git(*, args: list[str], cwd: Path, binary: bool = False) -> str | bytes:
    # git needs the inherited PATH for its own subcommands, so the env={"PATH": ""}
    # defense other subprocess calls use is unavailable; resolve and guard instead.
    found = shutil.which("git")
    if found is None:
        raise SystemExit("git was not found on PATH")
    git = Path(found)
    if not git.is_absolute():
        raise SystemExit(f"git resolved to a relative path: {git}")
    return subprocess.run(
        [git, *args], cwd=cwd, capture_output=True, text=not binary, check=True
    ).stdout


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_excluded(rel: str, excludes: list[str]) -> bool:
    # Exclude on path *segments* so "target" excludes "target/..." but not
    # "retargeted.txt". Excludes are repo-relative (or path-relative) prefixes.
    parts = rel.split("/")
    for ex in excludes:
        ex_parts = ex.strip("/").split("/")
        if parts[: len(ex_parts)] == ex_parts:
            return True
    return False


def _tree_files_worktree(base: Path, excludes: list[str]) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    for p in sorted(base.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(base).as_posix()
        if _is_excluded(rel, excludes):
            continue
        out.append((rel, p.read_bytes()))
    return out


def _tree_files_commit(
    path: str, commit: str, excludes: list[str]
) -> list[tuple[str, bytes]]:
    # `git ls-tree -r` enumerates blobs at the commit; read each via cat-file so
    # the hash is independent of the current working tree.
    spec = commit if path in (".", "") else f"{commit}:{path}"
    listing = _run_git(args=["ls-tree", "-r", "--format=%(path)", spec], cwd=REPO_ROOT)
    files: list[tuple[str, bytes]] = []
    prefix = "" if path in (".", "") else path.rstrip("/") + "/"
    for line in listing.splitlines():
        rel_in_subtree = line.strip()
        if not rel_in_subtree:
            continue
        if _is_excluded(rel_in_subtree, excludes):
            continue
        blob = _run_git(
            args=["cat-file", "-p", f"{commit}:{prefix}{rel_in_subtree}"],
            cwd=REPO_ROOT,
            binary=True,
        )
        files.append((rel_in_subtree, blob))
    return files


def _tree_hash(files: list[tuple[str, bytes]]) -> str:
    h = hashlib.sha256()
    for rel, content in sorted(files, key=lambda kv: kv[0]):
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(_sha256_bytes(content).encode("ascii"))
        h.update(b"\x00")
    return h.hexdigest()


def _hash_file(path: str, commit: str | None) -> tuple[str, bool]:
    """(sha256, reproducible). Reads from `commit` when given and the blob exists
    there; otherwise from the working tree (reproducible=False under a commit)."""
    if commit:
        try:
            blob = _run_git(
                args=["cat-file", "-p", f"{commit}:{path}"],
                cwd=REPO_ROOT,
                binary=True,
            )
            return _sha256_bytes(blob), True
        except subprocess.CalledProcessError:
            pass  # not committed at that revision — fall back to working tree
    fs = REPO_ROOT / path
    if not fs.is_file():
        raise FileNotFoundError(f"artifact not found: {path}")
    return _sha256_bytes(fs.read_bytes()), commit is None


def hash_item(item: dict, commit: str | None) -> dict:
    name = item["name"]
    kind = item.get("kind", "artifact")
    mode = item.get("mode", "file")
    path = item.get("path", name)
    excludes = item.get("exclude", [])

    if mode == "tree":
        # .git is not in any commit's tree (ls-tree on it returns nothing) and
        # is machine-specific in worktree mode — refs/objects differ per clone.
        # Skip it and identify repo state via HEAD commit SHA instead.
        if path.rstrip("/") == ".git":
            print(
                f"WARN: skipping {name!r} — .git is not in the commit tree and "
                "is machine-specific; record repo state via HEAD commit SHA instead",
                file=sys.stderr,
            )
            return {
                "name": name,
                "kind": kind,
                "skipped": True,
                "reason": ".git is not representable as a commit-tree hash; "
                "use HEAD commit SHA in your artifact spec instead",
            }
        if commit:
            files = _tree_files_commit(path, commit, excludes)
        else:
            files = _tree_files_worktree(REPO_ROOT / path, excludes)
        return {
            "name": name,
            "kind": kind,
            "sha256": _tree_hash(files),
            "file_count": len(files),
            "reproducible": commit is not None,
        }
    if mode == "file":
        sha, reproducible = _hash_file(path, commit)
        return {"name": name, "kind": kind, "sha256": sha, "reproducible": reproducible}
    raise ValueError(f"unknown artifact mode {mode!r} for {name!r}")


def _inline_into_html(html_path: Path, payload: dict) -> None:
    """Inline the payload into the report HTML between ARTIFACTS markers, mirroring
    extract_metrics.py's DATA-BEGIN/END pattern (offline-self-contained report)."""
    if not html_path.exists():
        print(
            f"WARN: --html {html_path} does not exist; skipping inline", file=sys.stderr
        )
        return
    html = html_path.read_text()
    inlined = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    new_block = f"<!-- ARTIFACTS-BEGIN -->{inlined}<!-- ARTIFACTS-END -->"
    patched, n = re.subn(
        r"<!--\s*ARTIFACTS-BEGIN\s*-->.*?<!--\s*ARTIFACTS-END\s*-->",
        lambda _m: new_block,
        html,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        print(
            "WARN: ARTIFACTS markers not found in HTML — skipping inline",
            file=sys.stderr,
        )
        return
    html_path.write_text(patched)
    print(f"Inlined artifacts into {html_path}", file=sys.stderr)


def build_payload(
    spec: dict, commit: str | None, generated_at: str | None = None
) -> dict:
    items = [hash_item(it, commit) for it in spec.get("items", [])]
    ts = (
        generated_at
        if generated_at is not None
        else datetime.now(tz=timezone.utc).isoformat()
    )
    payload: dict = {
        "commit": commit,
        "note": spec.get("note", ""),
        "items": items,
        "provenance": {
            "tool": "hash_artifacts.py",
            "method": "sha256; tree-hash = sha256 over sorted '<path>\\0<sha256>\\0'",
            "source": "git cat-file" if commit else "working tree",
        },
    }
    if ts:
        payload["generated_at"] = ts
    return payload


def main() -> int:
    global REPO_ROOT
    p = argparse.ArgumentParser(
        description="Hash provided artifacts into artifacts.json."
    )
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--spec", type=Path, required=True, help="artifacts spec JSON")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--commit", default=None, help="pin hashes to this commit via git")
    p.add_argument("--html", type=Path, default=None, help="report HTML to inline into")
    p.add_argument(
        "--generated-at",
        default=None,
        metavar="ISO8601",
        help="fix the generated_at timestamp (pass empty string to omit for byte-deterministic output)",
    )
    args = p.parse_args()

    REPO_ROOT = args.repo_root.resolve()
    if not (REPO_ROOT / ".git").exists():
        print(f"ERROR: {REPO_ROOT} is not a git repo (no .git/)", file=sys.stderr)
        return 1
    if args.commit:
        try:
            _run_git(
                args=["rev-parse", "--verify", "--quiet", f"{args.commit}^{{commit}}"],
                cwd=REPO_ROOT,
            )
        except subprocess.CalledProcessError:
            print(f"ERROR: --commit {args.commit!r} is not a commit", file=sys.stderr)
            return 1

    spec = json.loads(args.spec.read_text())
    payload = build_payload(spec, args.commit, args.generated_at)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {args.out}", file=sys.stderr)
    if args.html is not None:
        _inline_into_html(args.html, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
