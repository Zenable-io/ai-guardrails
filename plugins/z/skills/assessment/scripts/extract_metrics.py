# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Extract repo metrics from git history into metrics.json.

Usage:
    uv run --script extract_metrics.py \\
        --repo-root <path-to-target-repo> \\
        --out <path-to-metrics.json> \\
        [--html <path-to-index.html-to-inline-into>] \\
        [--cutoff-sha <sha>] \\
        [--aliases <path-to-aliases.json>] \\
        [--top-authors 20]

The aliases JSON is a list of lists; each inner list is one person with
the names exactly as they appear in `git log --format='%an'`:

    [["Jane Doe", "jdoe"], ["Sam Smith", "ssmith42"]]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SEP = "\x1f"  # ASCII unit separator — safe field delimiter
REC = "\x1e"  # ASCII record separator

# Populated by main() from CLI args so the module-level helpers (git(), etc.)
# can stay simple closures over a single repo root.
REPO_ROOT: Path = Path.cwd()


def _run_git(*, args: list[str], cwd: Path) -> str:
    # git needs the inherited PATH for its own subcommands, so the env={"PATH": ""}
    # defense other subprocess calls use is unavailable; resolve and guard instead.
    found = shutil.which("git")
    if found is None:
        raise SystemExit("git was not found on PATH")
    git = Path(found)
    if not git.is_absolute():
        raise SystemExit(f"git resolved to a relative path: {git}")
    return subprocess.run(
        [git, *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def collect_commits(cutoff_sha: str | None, path_prefix: str | None) -> list[dict]:
    """Walk every reachable commit (or up to `cutoff_sha` if given) and
    capture metadata + numstat totals. Uses `git log --numstat` in one pass
    so we don't spawn one subprocess per commit. Returns commits with
    `additions` and `deletions` populated; binary files contribute 0 to
    both (numstat emits '-').

    When `path_prefix` is set, history is scoped to commits that touched
    files under that prefix (relative to the repo root). This is what you
    want when running against a sub-package inside a monorepo — without it
    the metrics describe the whole repo, not the sub-package."""
    fmt = "\x02RECORD\x02" + SEP.join(["%H", "%an", "%ae", "%at", "%P", "%s"]) + REC
    target = cutoff_sha if cutoff_sha else "HEAD"
    log_args = ["log", "--numstat", f"--pretty=format:{fmt}", target]
    if path_prefix:
        log_args += ["--", path_prefix]
    raw = _run_git(args=log_args, cwd=REPO_ROOT)
    commits: list[dict] = []
    current: dict | None = None
    for line in raw.splitlines():
        if line.startswith("\x02RECORD\x02"):
            if current is not None:
                commits.append(current)
            payload = line[len("\x02RECORD\x02") :].rstrip(REC)
            parts = payload.split(SEP)
            if len(parts) < 6:
                current = None
                continue
            sha, name, email, ts, parents, subject = parts
            current = {
                "sha": sha,
                "author": name,
                "email": email,
                "ts": int(ts),
                "parents": parents.split() if parents else [],
                "subject": subject,
                "additions": 0,
                "deletions": 0,
            }
        elif current is not None and line.strip():
            # numstat row: "<adds>\t<dels>\t<path>"; binary = "-\t-\tpath"
            f = line.split("\t", 2)
            if len(f) >= 2:
                if f[0].isdigit():
                    current["additions"] += int(f[0])
                if f[1].isdigit():
                    current["deletions"] += int(f[1])
    if current is not None:
        commits.append(current)
    return commits


def percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    k = max(0, min(len(sorted_vals) - 1, round(pct * (len(sorted_vals) - 1))))
    return sorted_vals[k]


def compute_pr_durations(commits: list[dict]) -> list[dict]:
    """For every merge commit whose subject matches 'Merge pull request',
    estimate PR open duration as merge_time - earliest commit on the
    feature branch (after merge-base of the two parents)."""
    durations: list[dict] = []
    for c in commits:
        if len(c["parents"]) != 2:
            continue
        if "pull request" not in c["subject"].lower():
            continue
        p1, p2 = c["parents"]
        try:
            base = _run_git(args=["merge-base", p1, p2], cwd=REPO_ROOT).strip()
        except subprocess.CalledProcessError:
            continue
        if not base:
            continue
        try:
            log = _run_git(
                args=["log", "--reverse", "--pretty=format:%at", f"{base}..{p2}"],
                cwd=REPO_ROOT,
            )
        except subprocess.CalledProcessError:
            continue
        first = log.splitlines()[:1]
        if not first:
            continue
        first_ts = int(first[0])
        dur_s = c["ts"] - first_ts
        if dur_s < 0:
            continue
        durations.append(
            {
                "sha": c["sha"],
                "merged_at": c["ts"],
                "duration_hours": round(dur_s / 3600, 3),
                "subject": c["subject"],
            }
        )
    return durations


def month_key(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m")


_NOREPLY_PREFIX = re.compile(r"^\d+\+")


def _normalize_email(email: str) -> tuple[str, str]:
    """Returns (full_lower, local_lower_stripped). Local part has the
    GitHub `123456+` noreply prefix removed so '91565836+DSiravo@...'
    and 'dsiravo@...' collapse together."""
    e = (email or "").strip().lower()
    if "@" not in e:
        return e, ""
    local, _ = e.split("@", 1)
    local = _NOREPLY_PREFIX.sub("", local)
    return e, local


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


class _UnionFind:
    def __init__(self) -> None:
        self.p: dict = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def build_author_stats(
    commits: list[dict],
    manual_aliases: list[list[str]],
) -> tuple[list[dict], dict[tuple[str, str], str]]:
    """Group commits by author identity in one pass. Returns:

      - `authors`: aggregated per-person rows (commits, LoC, span, aliases)
      - `author_map`: every raw (name, email) commit identity → canonical
        display name, so downstream functions can join `commits` against the
        deduplicated identity without re-running the union-find.

    Two (name, email) pairs are treated as the same person if they share any of:
      - the same email (case-insensitive)
      - the same email local-part after stripping GitHub `\\d+\\+` prefix
      - the same name (case-insensitive, alphanumerics only)
      - explicit grouping via `manual_aliases` for the rare case where
        none of the above can collapse them automatically.
    Canonical display name is the variant with the most commits."""
    # First pass: collect raw (name, email) identities and their commits
    raw: dict[tuple[str, str], dict] = {}
    for c in commits:
        key = (c["author"], c["email"])
        rec = raw.setdefault(
            key,
            {
                "name": c["author"],
                "email": c["email"],
                "first_ts": c["ts"],
                "last_ts": c["ts"],
                "count": 0,
                "additions": 0,
                "deletions": 0,
            },
        )
        rec["first_ts"] = min(rec["first_ts"], c["ts"])
        rec["last_ts"] = max(rec["last_ts"], c["ts"])
        rec["count"] += 1
        rec["additions"] += c.get("additions", 0)
        rec["deletions"] += c.get("deletions", 0)

    # Build union-find across raw identities
    uf = _UnionFind()
    by_email: dict[str, tuple] = {}
    by_local: dict[str, tuple] = {}
    by_name: dict[str, tuple] = {}
    keys_by_name: dict[str, list] = defaultdict(list)
    for key in raw:
        uf.find(key)  # ensure node exists
        name, email = key
        full, local = _normalize_email(email)
        nname = _normalize_name(name)
        keys_by_name[name].append(key)
        if full:
            if full in by_email:
                uf.union(key, by_email[full])
            else:
                by_email[full] = key
        if local:
            if local in by_local:
                uf.union(key, by_local[local])
            else:
                by_local[local] = key
        if nname:
            if nname in by_name:
                uf.union(key, by_name[nname])
            else:
                by_name[nname] = key
    for group in manual_aliases:
        anchor = None
        for n in group:
            for k in keys_by_name.get(n, []):
                if anchor is None:
                    anchor = k
                else:
                    uf.union(anchor, k)

    # Aggregate groups
    groups: dict = defaultdict(
        lambda: {
            "names": defaultdict(int),
            "emails": set(),
            "first_ts": None,
            "last_ts": None,
            "count": 0,
            "additions": 0,
            "deletions": 0,
        }
    )
    for key, rec in raw.items():
        root = uf.find(key)
        g = groups[root]
        g["names"][rec["name"]] += rec["count"]
        if rec["email"]:
            g["emails"].add(rec["email"])
        g["first_ts"] = (
            rec["first_ts"]
            if g["first_ts"] is None
            else min(g["first_ts"], rec["first_ts"])
        )
        g["last_ts"] = (
            rec["last_ts"]
            if g["last_ts"] is None
            else max(g["last_ts"], rec["last_ts"])
        )
        g["count"] += rec["count"]
        g["additions"] += rec.get("additions", 0)
        g["deletions"] += rec.get("deletions", 0)

    out = []
    canonical_by_root: dict = {}
    for root, g in groups.items():
        canonical = max(g["names"].items(), key=lambda kv: kv[1])[0]
        canonical_by_root[root] = canonical
        aliases = sorted(n for n in g["names"] if n != canonical)
        out.append(
            {
                "author": canonical,
                "aliases": aliases,
                "emails": sorted(g["emails"]),
                "first_commit": datetime.fromtimestamp(
                    g["first_ts"], tz=timezone.utc
                ).strftime("%Y-%m-%d"),
                "last_commit": datetime.fromtimestamp(
                    g["last_ts"], tz=timezone.utc
                ).strftime("%Y-%m-%d"),
                "span_days": (g["last_ts"] - g["first_ts"]) // 86400,
                "commits": g["count"],
                "additions": g["additions"],
                "deletions": g["deletions"],
                "loc_changed": g["additions"] + g["deletions"],
            }
        )
    out.sort(key=lambda r: r["commits"], reverse=True)

    author_map = {key: canonical_by_root[uf.find(key)] for key in raw}
    return out, author_map


def build_cumulative_series(
    commits: list[dict],
    top_authors: list[str],
    author_map: dict[tuple[str, str], str],
) -> dict:
    """Monthly cumulative metrics per top author across two dimensions:
      - `series`     : cumulative commits
      - `loc_series` : cumulative LoC changed (additions + deletions)
    Both share the same `months` axis and null-padding before/after each
    author's active window."""
    top_set = set(top_authors)
    months = sorted({month_key(c["ts"]) for c in commits})
    # Generate full month range to avoid gaps in the racing chart
    if months:
        start_year, start_month = map(int, months[0].split("-"))
        end_year, end_month = map(int, months[-1].split("-"))
        full = []
        y, m = start_year, start_month
        while (y, m) <= (end_year, end_month):
            full.append(f"{y:04d}-{m:02d}")
            m += 1
            if m == 13:
                m = 1
                y += 1
        months = full

    per_month_commits: dict[str, dict[str, int]] = {
        a: defaultdict(int) for a in top_set
    }
    per_month_loc: dict[str, dict[str, int]] = {a: defaultdict(int) for a in top_set}
    first_month: dict[str, str] = {}
    last_month: dict[str, str] = {}
    for c in commits:
        canonical = author_map.get((c["author"], c["email"]), c["author"])
        if canonical in top_set:
            mk = month_key(c["ts"])
            per_month_commits[canonical][mk] += 1
            per_month_loc[canonical][mk] += c.get("additions", 0) + c.get(
                "deletions", 0
            )
            if canonical not in first_month or mk < first_month[canonical]:
                first_month[canonical] = mk
            if canonical not in last_month or mk > last_month[canonical]:
                last_month[canonical] = mk

    def cumulate(per_month: dict[str, dict[str, int]]) -> dict[str, list]:
        series: dict[str, list] = {}
        for a in top_authors:
            cum = 0
            row: list = []
            fm = first_month.get(a)
            lm = last_month.get(a)
            for mo in months:
                cum += per_month[a].get(mo, 0)
                if fm is not None and (mo < fm or mo > lm):
                    row.append(None)
                else:
                    row.append(cum)
            series[a] = row
        return series

    return {
        "months": months,
        "series": cumulate(per_month_commits),  # cumulative commits
        "loc_series": cumulate(per_month_loc),  # cumulative LoC changed
    }


def build_loc_per_month(commits: list[dict]) -> list[dict]:
    """Returns one row per month with totals across all commits:
      { month, additions, deletions, commits, mean_size }
    `mean_size` = (additions + deletions) / commits."""
    per: dict[str, dict] = defaultdict(
        lambda: {"additions": 0, "deletions": 0, "commits": 0}
    )
    for c in commits:
        mk = month_key(c["ts"])
        r = per[mk]
        r["additions"] += c.get("additions", 0)
        r["deletions"] += c.get("deletions", 0)
        r["commits"] += 1
    # backfill missing months so the chart has a continuous x-axis
    if per:
        keys = sorted(per.keys())
        start_year, start_month = map(int, keys[0].split("-"))
        end_year, end_month = map(int, keys[-1].split("-"))
        full: list[str] = []
        y, m = start_year, start_month
        while (y, m) <= (end_year, end_month):
            full.append(f"{y:04d}-{m:02d}")
            m += 1
            if m == 13:
                m, y = 1, y + 1
        out: list[dict] = []
        for mo in full:
            r = per.get(mo, {"additions": 0, "deletions": 0, "commits": 0})
            churn = r["additions"] + r["deletions"]
            mean = round(churn / r["commits"], 1) if r["commits"] else 0
            out.append(
                {
                    "month": mo,
                    "additions": r["additions"],
                    "deletions": r["deletions"],
                    "commits": r["commits"],
                    "mean_size": mean,
                }
            )
        return out
    return []


def yearly_counts(commits: list[dict], predicate=None) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for c in commits:
        if predicate is not None and not predicate(c):
            continue
        y = datetime.fromtimestamp(c["ts"], tz=timezone.utc).strftime("%Y")
        out[y] += 1
    return dict(sorted(out.items()))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract git-derived repo metrics.")
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Path to the git repo to analyze (default: cwd).",
    )
    p.add_argument(
        "--out", type=Path, required=True, help="Where to write metrics.json."
    )
    p.add_argument(
        "--html",
        type=Path,
        default=None,
        help="Optional path to an index.html with DATA-BEGIN/DATA-END "
        "markers to inline the metrics into.",
    )
    p.add_argument(
        "--cutoff-sha",
        default=None,
        help="Optional commit SHA to limit history to (excludes "
        "anything not reachable from this commit).",
    )
    p.add_argument(
        "--path-prefix",
        default=None,
        help="Optional repo-relative path to scope history to. "
        "Use this when scanning a sub-package inside a "
        "monorepo so metrics describe the sub-package's "
        "history, not the whole repo's.",
    )
    p.add_argument(
        "--aliases",
        type=Path,
        default=None,
        help="Optional JSON file containing manual author alias "
        "groups: a list of lists of author display names.",
    )
    p.add_argument(
        "--top-authors",
        type=int,
        default=20,
        help="How many top authors to include in the racing chart (default: 20).",
    )
    p.add_argument(
        "--generated-at",
        default=None,
        metavar="ISO8601",
        help="fix the generated_at timestamp (empty string to omit for byte-deterministic output)",
    )
    return p.parse_args()


def main() -> int:
    global REPO_ROOT
    args = parse_args()
    REPO_ROOT = args.repo_root.resolve()
    if not (REPO_ROOT / ".git").exists():
        print(f"ERROR: {REPO_ROOT} is not a git repo (no .git/)", file=sys.stderr)
        return 1

    manual_aliases: list[list[str]] = []
    if args.aliases is not None:
        manual_aliases = json.loads(args.aliases.read_text())

    if args.cutoff_sha is not None:
        try:
            _run_git(
                args=[
                    "rev-parse",
                    "--verify",
                    "--quiet",
                    f"{args.cutoff_sha}^{{commit}}",
                ],
                cwd=REPO_ROOT,
            )
        except subprocess.CalledProcessError:
            print(
                f"ERROR: --cutoff-sha {args.cutoff_sha!r} is not a commit in {REPO_ROOT}",
                file=sys.stderr,
            )
            return 1

    scope_msg = f" (scoped to {args.path_prefix})" if args.path_prefix else ""
    print(f"Collecting commits from {REPO_ROOT}{scope_msg}...", file=sys.stderr)
    commits = collect_commits(args.cutoff_sha, args.path_prefix)
    print(f"  {len(commits)} commits", file=sys.stderr)
    if not commits:
        print("ERROR: no commits found", file=sys.stderr)
        return 1

    print("Building author stats...", file=sys.stderr)
    authors, author_map = build_author_stats(commits, manual_aliases)

    top_authors = [a["author"] for a in authors[: args.top_authors]]
    print(
        f"Building cumulative series for top {len(top_authors)} authors...",
        file=sys.stderr,
    )
    cumulative = build_cumulative_series(commits, top_authors, author_map)

    print("Computing PR durations (this walks every merge commit)...", file=sys.stderr)
    pr_durations = compute_pr_durations(commits)
    dur_vals = sorted(d["duration_hours"] for d in pr_durations)
    pr_stats = {
        "total_pr_merges": len(pr_durations),
        "mean_hours": round(sum(dur_vals) / len(dur_vals), 2) if dur_vals else 0,
        "median_hours": round(percentile(dur_vals, 0.50), 2),
        "p25_hours": round(percentile(dur_vals, 0.25), 2),
        "p75_hours": round(percentile(dur_vals, 0.75), 2),
        "p90_hours": round(percentile(dur_vals, 0.90), 2),
        "p95_hours": round(percentile(dur_vals, 0.95), 2),
        "max_hours": round(dur_vals[-1], 2) if dur_vals else 0,
        "min_hours": round(dur_vals[0], 2) if dur_vals else 0,
        "closed_lt_1_day_pct": round(
            100 * sum(1 for d in dur_vals if d < 24) / len(dur_vals), 1
        )
        if dur_vals
        else 0,
        "closed_lt_1_week_pct": round(
            100 * sum(1 for d in dur_vals if d < 168) / len(dur_vals), 1
        )
        if dur_vals
        else 0,
        "closed_lt_1_month_pct": round(
            100 * sum(1 for d in dur_vals if d < 720) / len(dur_vals), 1
        )
        if dur_vals
        else 0,
    }

    revert_count = sum(1 for c in commits if c["subject"].lower().startswith("revert"))
    fix_count = sum(
        1
        for c in commits
        if c["subject"].lower().startswith("fix") or "hotfix" in c["subject"].lower()
    )

    summary = {
        "total_commits": len(commits),
        "total_merge_commits": sum(1 for c in commits if len(c["parents"]) >= 2),
        "total_pr_merges": pr_stats["total_pr_merges"],
        "uses_pr_workflow": pr_stats["total_pr_merges"] > 0,
        "pr_merges_pct_of_commits": round(
            100 * pr_stats["total_pr_merges"] / len(commits), 1
        )
        if commits
        else 0,
        "first_commit": authors[-1]["first_commit"] if authors else None,
        "unique_authors": len(authors),
        "revert_commits": revert_count,
        "fix_commits": fix_count,
        "change_failure_rate_pct": round(
            100 * revert_count / pr_stats["total_pr_merges"], 2
        )
        if pr_stats["total_pr_merges"]
        else 0,
    }
    earliest = min(c["ts"] for c in commits)
    latest = max(c["ts"] for c in commits)
    summary["first_commit"] = datetime.fromtimestamp(
        earliest, tz=timezone.utc
    ).strftime("%Y-%m-%d")
    summary["last_commit"] = datetime.fromtimestamp(latest, tz=timezone.utc).strftime(
        "%Y-%m-%d"
    )

    dora = {
        "commits_per_year": yearly_counts(commits),
        "merges_per_year": yearly_counts(
            commits, predicate=lambda c: len(c["parents"]) >= 2
        ),
        "pr_merges_per_year": yearly_counts(
            commits,
            predicate=lambda c: (
                len(c["parents"]) == 2 and "pull request" in c["subject"].lower()
            ),
        ),
    }

    payload = {
        "summary": summary,
        "pr_stats": pr_stats,
        "dora": dora,
        "authors": authors,
        "racing_chart": cumulative,
        "loc_per_month": build_loc_per_month(commits),
        "provenance": {
            "tool": "extract_metrics.py",
            "source": "git log --numstat",
            "cutoff_sha": args.cutoff_sha,
            "path_prefix": args.path_prefix,
            "manual_aliases": manual_aliases,
        },
    }
    generated_at = (
        args.generated_at
        if args.generated_at is not None
        else datetime.now(tz=timezone.utc).isoformat()
    )
    if generated_at:
        payload["generated_at"] = generated_at

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {args.out}", file=sys.stderr)

    if args.html is not None:
        if not args.html.exists():
            print(
                f"WARN: --html {args.html} does not exist; skipping inline",
                file=sys.stderr,
            )
            return 0
        html = args.html.read_text()
        # Escape every `<` so untrusted git-derived strings can't close the
        # <script> block or recreate DATA-BEGIN/DATA-END markers on re-run.
        inlined = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
        new_block = f"<!-- DATA-BEGIN -->{inlined}<!-- DATA-END -->"
        patched, n = re.subn(
            r"<!--\s*DATA-BEGIN\s*-->.*?<!--\s*DATA-END\s*-->",
            lambda _m: new_block,
            html,
            count=1,
            flags=re.DOTALL,
        )
        if n == 0:
            print(
                "WARN: DATA markers not found in index.html — skipping inline",
                file=sys.stderr,
            )
        else:
            args.html.write_text(patched)
            print(f"Inlined metrics into {args.html}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
