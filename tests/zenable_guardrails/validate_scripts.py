#!/usr/bin/env python3
"""Drive the prfeedback shell scripts against a stub `gh` and check what they do.

These scripts only ever ran against live GitHub, which meant the failure modes that
mattered went unnoticed: a PR with nothing unresolved crashed the dump halfway
through its XML, and a thread that did not match sent an empty node ID to a
mutation instead of reporting "not found". Both are exercised here, offline.

`mark-addressed.sh` posts a public comment when it succeeds, so the stub matters for
a second reason -- the log it writes is how a test asserts that no mutation was sent.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "plugins" / "z" / "skills" / "prfeedback" / "scripts"
DUMP = SCRIPTS / "dump-unresolved-comments.sh"
MARK = SCRIPTS / "mark-addressed.sh"
STUB = Path(__file__).resolve().parent / "gh_stub.py"

errors: list[str] = []


def ok(message: str) -> None:
    print(f"✓ {message}")


def fail(message: str) -> None:
    errors.append(message)
    print(f"❌ {message}")


def thread(path: str, line: int | None, *, resolved: bool = False, body: str = "a comment",
           author: str | None = "reviewer", thread_id: str = "PRRT_stub") -> dict:
    return {
        "id": thread_id,
        "isResolved": resolved,
        "path": path,
        "line": line,
        "startLine": line,
        "comments": {"nodes": [{"author": None if author is None else {"login": author}, "body": body}]},
    }


def page(nodes: list[dict], *, end_cursor: str | None = None, serves_cursor: str | None = None) -> dict:
    result = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": end_cursor is not None, "endCursor": end_cursor},
                        "nodes": nodes,
                    }
                }
            }
        }
    }
    if serves_cursor is not None:
        result["_cursor"] = serves_cursor
    return result


def run(script: Path, args: list[str], pages: list[dict], *, owner: str = "Zenable-io",
        name: str = "ai-guardrails", mutation: dict | None = None) -> tuple[int, str, str, list[dict]]:
    """Run a script with `gh` stubbed out; return rc, stdout, stderr, and the call log."""
    with tempfile.TemporaryDirectory() as workspace:
        work = Path(workspace)
        fixture = {"repo": {"owner": {"login": owner}, "name": name}, "pages": pages}
        if mutation is not None:
            fixture["mutation"] = mutation
        fixture_path = work / "fixture.json"
        fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

        bin_dir = work / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        shutil.copy(STUB, gh)
        gh.chmod(0o755)

        log_path = work / "calls.jsonl"
        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GH_STUB_FIXTURE": str(fixture_path),
            "GH_STUB_LOG": str(log_path),
        }
        # Both scripts loop until pageInfo says otherwise, so a paging regression hangs
        # rather than failing. Report that as an ordinary failed check, not a traceback.
        try:
            completed = subprocess.run(
                [str(script), *args], capture_output=True, text=True, env=env, timeout=30
            )
            returncode, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
        except subprocess.TimeoutExpired:
            returncode, stdout, stderr = 124, "", f"{script.name} did not terminate within 30s"

        calls = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line
        ] if log_path.exists() else []
        return returncode, stdout, stderr, calls


def graphql_calls(calls: list[dict]) -> list[dict]:
    return [c for c in calls if c["argv"][:2] == ["api", "graphql"]]


def mutations(calls: list[dict]) -> list[dict]:
    return [c for c in graphql_calls(calls) if c["variables"].get("query", "").lstrip().startswith("mutation")]


def check_dump_with_no_unresolved_threads() -> None:
    """The regression that mattered most: a clean PR used to die mid-document.

    `jq` emitted nothing, the `grep -v` that trimmed blank lines exited 1, and
    `pipefail` tore the script down before it printed its closing tags.
    """
    rc, out, err, _ = run(DUMP, ["22"], [page([thread("a.py", 5, resolved=True)])])
    if rc != 0:
        fail(f"dump: PR with nothing unresolved exited {rc} (expected 0): {err.strip()}")
        return
    try:
        root = ElementTree.fromstring(out)
    except ElementTree.ParseError as exc:
        fail(f"dump: PR with nothing unresolved produced malformed XML: {exc}")
        return
    if root.find("threads") is None or len(root.find("threads")) != 0:
        fail("dump: PR with nothing unresolved should emit an empty <threads> element")
        return
    ok("dump: a PR with nothing unresolved exits 0 with a complete, empty document")


def check_dump_renders_threads() -> None:
    rc, out, err, _ = run(DUMP, ["24"], [page([
        thread("src/a.py", 118, body="line-level finding"),
        thread("src/b.py", None, body="file-level finding"),
        thread("src/c.py", 7, resolved=True, body="already handled"),
    ])])
    if rc != 0:
        fail(f"dump: exited {rc} on a populated PR: {err.strip()}")
        return
    root = ElementTree.fromstring(out)
    threads = root.find("threads")
    files = [t.findtext("file") for t in threads]
    if files != ["src/a.py", "src/b.py"]:
        fail(f"dump: expected only the unresolved threads, got {files}")
        return
    if threads[0].findtext("line") != "118":
        fail("dump: line-level thread lost its <line> element")
        return
    if threads[1].find("line") is not None:
        fail("dump: file-level thread should have no <line> element")
        return
    bodies = [c.findtext("body") for t in threads for c in t.find("comments")]
    if bodies != ["line-level finding", "file-level finding"]:
        fail(f"dump: comment bodies did not round-trip, got {bodies}")
        return
    ok("dump: renders unresolved line-level and file-level threads, skipping resolved ones")


def check_dump_paginates() -> None:
    rc, out, err, calls = run(DUMP, ["24"], [
        page([thread("first.py", 1, body="page one")], end_cursor="CURSOR1"),
        page([thread("second.py", 2, body="page two")], serves_cursor="CURSOR1"),
    ])
    if rc != 0:
        fail(f"dump: exited {rc} while paginating: {err.strip()}")
        return
    files = [t.findtext("file") for t in ElementTree.fromstring(out).find("threads")]
    if files != ["first.py", "second.py"]:
        fail(f"dump: pagination dropped threads, got {files}")
        return
    if len(graphql_calls(calls)) != 2:
        fail(f"dump: expected 2 GraphQL requests while paginating, saw {len(graphql_calls(calls))}")
        return
    ok("dump: follows pageInfo.endCursor and concatenates every page")


def check_dump_escapes_cdata() -> None:
    """A review comment is written by whoever reviewed the PR, so it is untrusted."""
    hostile = "before ]]> after"
    rc, out, _, _ = run(DUMP, ["24"], [page([thread("a.py", 1, body=hostile)])])
    if rc != 0:
        fail(f"dump: exited {rc} on a body containing ]]>")
        return
    try:
        root = ElementTree.fromstring(out)
    except ElementTree.ParseError as exc:
        fail(f"dump: a body containing ]]> broke the document: {exc}")
        return
    recovered = root.find("threads")[0].find("comments")[0].findtext("body")
    if recovered != hostile:
        fail(f"dump: ]]> in a body did not round-trip, got {recovered!r}")
        return
    ok("dump: a comment body containing ]]> stays inside its CDATA section")


def check_dump_handles_deleted_author() -> None:
    rc, out, err, _ = run(DUMP, ["24"], [page([thread("a.py", 1, author=None)])])
    if rc != 0:
        fail(f"dump: exited {rc} when a comment author was null: {err.strip()}")
        return
    author = ElementTree.fromstring(out).find("threads")[0].find("comments")[0].findtext("author")
    if author != "unknown":
        fail(f"dump: a null author should render as 'unknown', got {author!r}")
        return
    ok("dump: a comment from a deleted account renders as 'unknown'")


def check_graphql_values_are_variables() -> None:
    """Repo and PR values must travel as typed variables, not spliced into the query."""
    hostile_repo = 'evil") { x } #'
    rc, _, _, calls = run(
        DUMP, ["24"], [page([])], owner="octocat", name=hostile_repo
    )
    if rc != 0:
        fail(f"dump: exited {rc} against a repository name containing quotes")
        return
    call = graphql_calls(calls)[0]
    if hostile_repo in call["variables"].get("query", ""):
        fail("dump: repository name was interpolated into the GraphQL query text")
        return
    if call["variables"].get("repo") != hostile_repo:
        fail("dump: repository name was not passed as a GraphQL variable")
        return
    if "$owner" not in call["variables"].get("query", ""):
        fail("dump: query does not declare GraphQL variables")
        return
    ok("dump: owner, repo, and PR number travel as GraphQL variables, not query text")


def check_dump_rejects_bad_pr_numbers() -> None:
    for bad in ['1) { } mutation {', "abc", "-5"]:
        rc, _, _, calls = run(DUMP, [bad], [page([])])
        if rc == 0:
            fail(f"dump: accepted a non-numeric PR number {bad!r}")
            return
        if calls:
            fail(f"dump: reached the network with a non-numeric PR number {bad!r}")
            return
    rc, _, _, _ = run(DUMP, [], [page([])])
    if rc != 1:
        fail(f"dump: missing argument should exit 1, got {rc}")
        return
    ok("dump: rejects a missing or non-numeric PR number before any request")


def check_mark_reports_missing_thread() -> None:
    """The not-found branch was unreachable, so this used to fail inside the mutation."""
    rc, _, err, calls = run(
        MARK, ["24", "does/not/exist.py", "5", "abc123f"], [page([thread("other.py", 5)])]
    )
    if rc != 1:
        fail(f"mark: a missing thread should exit 1, got {rc}")
        return
    if "Could not find unresolved thread" not in err:
        fail(f"mark: a missing thread should say so; stderr was {err.strip()!r}")
        return
    if mutations(calls):
        fail("mark: attempted a mutation despite finding no matching thread")
        return
    ok("mark: a missing thread reports the error and sends no mutation")


def check_mark_posts_to_the_matching_thread() -> None:
    rc, _, err, calls = run(
        MARK, ["24", "src/a.py", "118", "--comment", "looks intentional"],
        [page([thread("src/a.py", 118, thread_id="PRRT_target"), thread("src/b.py", 9, thread_id="PRRT_other")])],
    )
    if rc != 0:
        fail(f"mark: exited {rc} on a matching thread: {err.strip()}")
        return
    sent = mutations(calls)
    if len(sent) != 1:
        fail(f"mark: expected exactly 1 mutation, saw {len(sent)}")
        return
    if sent[0]["variables"].get("threadId") != "PRRT_target":
        fail(f"mark: posted to the wrong thread: {sent[0]['variables'].get('threadId')!r}")
        return
    if sent[0]["variables"].get("body") != "looks intentional":
        fail(f"mark: comment body did not round-trip: {sent[0]['variables'].get('body')!r}")
        return
    ok("mark: posts one reply to the thread matching the path and line")


def check_mark_preserves_hostile_comment_bodies() -> None:
    """The body used to be spliced into the mutation, so a quote broke the query."""
    hostile = 'He said "no" \\ then {left}\nsecond line'
    rc, _, err, calls = run(
        MARK, ["24", "src/a.py", "-", "--comment", hostile],
        [page([thread("src/a.py", None, thread_id="PRRT_file")])],
    )
    if rc != 0:
        fail(f"mark: exited {rc} on a body containing quotes: {err.strip()}")
        return
    body = mutations(calls)[0]["variables"].get("body")
    if body != hostile:
        fail(f"mark: a body with quotes and newlines did not round-trip, got {body!r}")
        return
    ok("mark: a comment body with quotes, backslashes, and newlines round-trips intact")


def check_mark_commit_mode_body() -> None:
    rc, _, err, calls = run(
        MARK, ["24", "src/a.py", "118", "abc123f4567890"],
        [page([thread("src/a.py", 118, thread_id="PRRT_target")])],
    )
    if rc != 0:
        fail(f"mark: exited {rc} in commit mode: {err.strip()}")
        return
    body = mutations(calls)[0]["variables"].get("body")
    if "abc123f" not in body or "abc123f4" in body:
        fail(f"mark: commit mode should cite the 7-character short hash, got {body!r}")
        return
    if "\\n" in body or "\n" not in body:
        fail(f"mark: commit mode body should contain real newlines, got {body!r}")
        return
    ok("mark: commit mode cites the short hash with real newlines")


def check_mark_thread_index() -> None:
    pages = [page([
        thread("src/a.py", None, thread_id="PRRT_one"),
        thread("src/a.py", None, thread_id="PRRT_two"),
    ])]
    rc, _, err, calls = run(MARK, ["24", "src/a.py", "-", "abc123f", "2"], pages)
    if rc != 0:
        fail(f"mark: exited {rc} selecting the second thread: {err.strip()}")
        return
    if mutations(calls)[0]["variables"].get("threadId") != "PRRT_two":
        fail("mark: thread index 2 did not select the second matching thread")
        return

    rc, _, err, calls = run(MARK, ["24", "src/a.py", "-", "abc123f", "9"], pages)
    if rc != 1:
        fail(f"mark: an out-of-range thread index should exit 1, got {rc}")
        return
    if mutations(calls):
        fail("mark: attempted a mutation with an out-of-range thread index")
        return
    ok("mark: selects a thread by index and refuses an out-of-range one")


def check_mark_rejects_bad_arguments() -> None:
    cases: list[tuple[list[str], str]] = [
        ([], "no arguments"),
        (["24", "a.py", "5", "--comment"], "--comment with no body"),
        (['1) { } mutation {', "a.py", "5", "abc123f"], "a non-numeric PR number"),
        (["24", "a.py", "notaline", "abc123f"], "a non-numeric line"),
    ]
    for args, label in cases:
        rc, _, _, calls = run(MARK, args, [page([])])
        if rc != 1:
            fail(f"mark: {label} should exit 1, got {rc}")
            return
        if mutations(calls):
            fail(f"mark: {label} still reached a mutation")
            return
    ok("mark: rejects missing, non-numeric, and malformed arguments before mutating")


def check_no_bash4_builtins() -> None:
    """macOS still ships bash 3.2, which has no `mapfile`."""
    for script in (DUMP, MARK):
        text = script.read_text(encoding="utf-8")
        for builtin in ("mapfile", "readarray"):
            # The rewrite explains in a comment why mapfile is gone, so only look at code.
            code = "\n".join(
                line for line in text.splitlines() if not line.lstrip().startswith("#")
            )
            if f"{builtin} " in code:
                fail(f"{script.name}: uses `{builtin}`, which bash 3.2 does not provide")
                return
    ok("both scripts avoid bash 4 builtins, so they run on the bash macOS ships")


def check_packaged_copies_match() -> None:
    """`scripts/` at the repo root duplicates the packaged copies; drift is silent."""
    for script in (DUMP, MARK):
        root_copy = REPO_ROOT / "scripts" / script.name
        if not root_copy.is_file():
            continue
        if root_copy.read_bytes() != script.read_bytes():
            fail(f"scripts/{script.name} has drifted from the packaged copy in {SCRIPTS.relative_to(REPO_ROOT)}")
            return
    ok("the repo-root script copies match the packaged ones byte for byte")


def main() -> int:
    print("Validating the prfeedback scripts against a stubbed gh...")
    for script in (DUMP, MARK):
        if not script.is_file():
            fail(f"missing script: {script.relative_to(REPO_ROOT)}")
            return 1
        if not os.access(script, os.X_OK):
            fail(f"{script.relative_to(REPO_ROOT)} is not executable")

    print("\n== dump-unresolved-comments.sh ==")
    check_dump_with_no_unresolved_threads()
    check_dump_renders_threads()
    check_dump_paginates()
    check_dump_escapes_cdata()
    check_dump_handles_deleted_author()
    check_graphql_values_are_variables()
    check_dump_rejects_bad_pr_numbers()

    print("\n== mark-addressed.sh ==")
    check_mark_reports_missing_thread()
    check_mark_posts_to_the_matching_thread()
    check_mark_preserves_hostile_comment_bodies()
    check_mark_commit_mode_body()
    check_mark_thread_index()
    check_mark_rejects_bad_arguments()

    print("\n== Portability and packaging ==")
    check_no_bash4_builtins()
    check_packaged_copies_match()

    print()
    if errors:
        print(f"Script validation FAILED with {len(errors)} error(s).")
        return 1
    print("Script validation passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
