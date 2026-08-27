"""Unit tests for hash_artifacts.py (deterministic artifact hashing for Appendix A).

Run from the skill scripts dir:  uv run --with pytest pytest tests/
"""

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import load_script

ha = load_script("hash_artifacts")

# Absolute, is_absolute()-validated git path passed directly to subprocess (no
# str() wrap, never resolved through PATH) — see the
# require-absolute-path-in-subprocess policy.
_GIT = Path(shutil.which("git") or "")
if not _GIT.is_absolute():
    raise RuntimeError("git executable not found on PATH")


def _git(repo: Path, *args: str) -> None:
    subprocess.run([_GIT, *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "Test")
    (r / "a.txt").write_bytes(b"hello\n")
    (r / "sub").mkdir()
    (r / "sub" / "b.txt").write_bytes(b"world\n")
    (r / "target").mkdir()
    (r / "target" / "junk.bin").write_bytes(b"BUILD ARTIFACT\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "init")
    return r


@pytest.mark.unit
def test_file_mode_is_plain_sha256(repo: Path) -> None:
    ha.REPO_ROOT = repo
    item = ha.hash_item(
        {"name": "a.txt", "kind": "src", "mode": "file", "path": "a.txt"}, None
    )
    assert item["sha256"] == hashlib.sha256(b"hello\n").hexdigest()
    assert item["reproducible"] is True  # no commit pin → read working tree


@pytest.mark.unit
def test_tree_mode_excludes_and_is_deterministic(repo: Path) -> None:
    ha.REPO_ROOT = repo
    spec_item = {
        "name": "tree",
        "kind": "src",
        "mode": "tree",
        "path": ".",
        "exclude": ["target", ".git"],
    }
    first = ha.hash_item(spec_item, None)
    second = ha.hash_item(spec_item, None)
    assert first == second  # deterministic
    assert first["file_count"] == 2  # a.txt + sub/b.txt; target/ and .git/ excluded

    # Expected tree-hash, computed independently from the documented construction.
    h = hashlib.sha256()
    for rel, content in sorted([("a.txt", b"hello\n"), ("sub/b.txt", b"world\n")]):
        h.update(rel.encode())
        h.update(b"\x00")
        h.update(hashlib.sha256(content).hexdigest().encode())
        h.update(b"\x00")
    assert first["sha256"] == h.hexdigest()


@pytest.mark.unit
def test_exclude_matches_path_segments_not_substrings(repo: Path) -> None:
    (repo / "retargeted.txt").write_bytes(b"keep me\n")
    ha.REPO_ROOT = repo
    item = ha.hash_item(
        {"name": "t", "mode": "tree", "path": ".", "exclude": ["target", ".git"]}, None
    )
    # "target" must not exclude "retargeted.txt" (substring), only the target/ dir.
    assert item["file_count"] == 3  # a.txt, sub/b.txt, retargeted.txt


@pytest.mark.unit
def test_git_directory_skipped_in_tree_mode(repo: Path) -> None:
    ha.REPO_ROOT = repo
    item = ha.hash_item(
        {"name": ".git (vcs)", "kind": "vcs", "mode": "tree", "path": ".git"}, None
    )
    assert item.get("skipped") is True
    assert "sha256" not in item
    # Same behavior under commit mode (where it would produce an empty tree hash).
    head = subprocess.run(
        [_GIT, "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    item_commit = ha.hash_item(
        {"name": ".git (vcs)", "kind": "vcs", "mode": "tree", "path": ".git"}, head
    )
    assert item_commit.get("skipped") is True


@pytest.mark.unit
def test_commit_mode_is_reproducible_and_ignores_worktree(repo: Path) -> None:
    ha.REPO_ROOT = repo
    head = subprocess.run(
        [_GIT, "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    pinned = ha.hash_item({"name": "a.txt", "mode": "file", "path": "a.txt"}, head)
    # Dirty the working tree; the committed hash must not move.
    (repo / "a.txt").write_bytes(b"TAMPERED\n")
    pinned_again = ha.hash_item(
        {"name": "a.txt", "mode": "file", "path": "a.txt"}, head
    )
    assert (
        pinned["sha256"]
        == pinned_again["sha256"]
        == hashlib.sha256(b"hello\n").hexdigest()
    )
    assert pinned["reproducible"] is True


@pytest.mark.unit
def test_uncommitted_file_under_commit_flags_not_reproducible(repo: Path) -> None:
    ha.REPO_ROOT = repo
    head = subprocess.run(
        [_GIT, "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (repo / "oob.jar").write_bytes(b"out of band\n")  # never committed
    item = ha.hash_item({"name": "oob.jar", "mode": "file", "path": "oob.jar"}, head)
    assert item["sha256"] == hashlib.sha256(b"out of band\n").hexdigest()
    assert item["reproducible"] is False  # not in the pinned commit


@pytest.mark.unit
def test_inline_into_html_replaces_markers(repo: Path, tmp_path: Path) -> None:
    html = tmp_path / "index.html"
    html.write_text(
        '<script id="artifacts-data" type="application/json">'
        "<!-- ARTIFACTS-BEGIN -->null<!-- ARTIFACTS-END --></script>"
    )
    ha._inline_into_html(html, {"items": [{"name": "x", "sha256": "abc"}]})
    out = html.read_text()
    assert '"name":"x"' in out
    assert "ARTIFACTS-BEGIN" in out and "ARTIFACTS-END" in out
    # The < of any nested tag is escaped so the payload can't break out of <script>.
    ha._inline_into_html(html, {"note": "a <script> b"})
    assert "\\u003cscript" in html.read_text()
