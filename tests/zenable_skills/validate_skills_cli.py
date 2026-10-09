#!/usr/bin/env python3
"""Check that the `skills` CLI (`npx skills add Zenable-io/skills`) finds every skill.

The CLI discovers skills through `.claude-plugin/marketplace.json` and its own
directory walk, not through anything this repo controls directly, so a layout or
manifest change can silently hide a skill from `npx skills` users while the plugin
itself still loads. The CLI version is pinned so an upstream release cannot turn
this red without a change here.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "plugins" / "z" / "skills"
SKILLS_CLI = "skills@1.7.2"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def main() -> int:
    npx = shutil.which("npx")
    if npx is None:
        print("✗ npx is required to exercise the skills CLI")
        return 1

    expected = sorted(p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())
    # A non-TTY run still draws its prompt frame; NO_COLOR keeps the parse simple.
    env = {**os.environ, "NO_COLOR": "1", "CI": "1"}
    result = subprocess.run(
        [npx, "-y", SKILLS_CLI, "add", str(REPO_ROOT), "--list"],
        capture_output=True, text=True, env=env, timeout=300, check=False,
    )
    output = ANSI.sub("", result.stdout + result.stderr)
    if result.returncode != 0:
        print(output)
        print(f"✗ `npx {SKILLS_CLI} add --list` exited {result.returncode}")
        return 1

    # Each listed skill is a line holding only its name, indented under the frame.
    listed = {m.group(1) for m in re.finditer(r"^│\s+([a-z0-9][a-z0-9-]*)\s*$", output, re.MULTILINE)}
    missing = [name for name in expected if name not in listed]
    if missing:
        print(output)
        print(f"✗ skills CLI did not list: {', '.join(missing)}")
        return 1

    print(f"✓ {SKILLS_CLI} lists all {len(expected)} skills")
    return 0


if __name__ == "__main__":
    sys.exit(main())
