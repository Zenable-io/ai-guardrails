# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Aggregate per-experiment result JSON into experiments.json (report evidence).

Demonstrated-attack stats (recovery rates, wall-clock, candidate-space size,
cost) get restated in attack-path and finding prose. Re-typing them drifts, so
each experiment script emits its OWN numbers as a small result JSON and this tool
validates + aggregates them; the report prose then injects from experiments.json
rather than re-typing.

Usage:
    uv run --script collect_experiments.py \\
        --experiments-dir <workspace/experiments> \\
        --out <experiments.json> \\
        [--html <index.html-to-inline-into>]

Per-experiment result schema (each experiment script writes one
``*.experiment.json``). The experiment OWNS its numbers — this tool never parses
``.out`` text, which is exactly the drift it removes:

    {
      "id": "AP-1",                         # required, stable; referenced from prose
      "name": "...",                        # required
      "command": "python attacks/attack_easy.py ...",   # optional, as run
      "ran_at": "2026-06-19T...Z",          # optional ISO-8601
      "metrics": {                          # optional; arbitrary name -> value
        "recovered": "8/8", "wall_clock_s": 30.0,
        "candidate_space": 4096, "cost_usd": 0.01
      },
      "summary": "...",                     # optional
      "evidence": ["experiments/attacks/attack_easy.out"]  # optional
    }

The report references a metric by indexing the experiments array by id:
``experiments.experiments.find(e => e.id === "AP-1").metrics.recovered``
so a number lives in exactly one place — the experiment that produced it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_REQUIRED = ("id", "name")


def load_experiment(path: Path) -> dict:
    doc = json.loads(path.read_text())
    missing = [k for k in _REQUIRED if not doc.get(k)]
    if missing:
        raise ValueError(
            f"{path.name}: missing required field(s): {', '.join(missing)}"
        )
    return {
        "id": doc["id"],
        "name": doc["name"],
        "command": doc.get("command") or None,
        "ran_at": doc.get("ran_at") or None,
        "metrics": doc.get("metrics") or {},
        "summary": doc.get("summary") or "",
        "evidence": list(doc.get("evidence") or []),
        "source": path.name,
    }


def _discover(experiments_dir: Path) -> list[Path]:
    return sorted(experiments_dir.rglob("*.experiment.json"))


def build_payload(files: list[Path], generated_at: str | None = None) -> dict:
    experiments = [load_experiment(p) for p in files]
    experiments.sort(key=lambda e: e["id"])
    seen: set[str] = set()
    for e in experiments:
        if e["id"] in seen:
            raise ValueError(f"duplicate experiment id {e['id']!r}")
        seen.add(e["id"])
    ts = (
        generated_at
        if generated_at is not None
        else datetime.now(tz=timezone.utc).isoformat()
    )
    payload: dict = {"experiments": experiments}
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
    new_block = f"<!-- EXPERIMENTS-BEGIN -->{inlined}<!-- EXPERIMENTS-END -->"
    patched, n = re.subn(
        r"<!--\s*EXPERIMENTS-BEGIN\s*-->.*?<!--\s*EXPERIMENTS-END\s*-->",
        lambda _m: new_block,
        html,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        print(
            "WARN: EXPERIMENTS markers not found in HTML — skipping inline",
            file=sys.stderr,
        )
        return
    html_path.write_text(patched)
    print(f"Inlined experiments into {html_path}", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(description="per-experiment JSON -> experiments.json")
    p.add_argument("--experiments-dir", type=Path, help="dir of *.experiment.json")
    p.add_argument(
        "--file", type=Path, nargs="*", help="explicit *.experiment.json files"
    )
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--html", type=Path, default=None)
    p.add_argument(
        "--generated-at",
        default=None,
        metavar="ISO8601",
        help="fix the generated_at timestamp (empty string to omit for byte-deterministic output)",
    )
    args = p.parse_args()

    files = list(args.file or [])
    if args.experiments_dir:
        files += _discover(args.experiments_dir)
    if not files:
        print(
            "ERROR: no *.experiment.json found (pass --experiments-dir or --file)",
            file=sys.stderr,
        )
        return 1

    payload = build_payload(files, args.generated_at)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(
        f"Wrote {args.out}: {len(payload['experiments'])} experiment(s)",
        file=sys.stderr,
    )
    if args.html is not None:
        _inline_into_html(args.html, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
