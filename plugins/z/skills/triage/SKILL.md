---
name: triage
description: Fetch and address unresolved Zenable AI guardrails review comments on the current pull request (GitHub PR) or merge request (GitLab MR). Use this skill whenever the user says "triage", "address PR feedback", "fix review comments", "respond to the guardrails bot", or anything about responding to automated code review feedback on a pull/merge request. Also trigger on /triage.
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
---

# Triage

Address unresolved review comments from the Zenable AI guardrails bot on the pull request (GitHub) or merge request (GitLab) for the current branch.

## Prerequisites

This skill requires the Zenable CLI. Check whether it's installed:

zenable CLI location: !`command -v zenable 2>/dev/null || echo "NOT INSTALLED"`

If the above shows "NOT INSTALLED", install it by running this skill's bundled
installer (idempotent — a no-op once the CLI is present):

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/triage/scripts/install-zenable.sh"
```

The script delegates to the canonical installer at
[cli.zenable.app/install.sh](https://cli.zenable.app), which verifies the
download (checksum + signature) before installing. It needs `curl` or `wget`.
If you'd rather install manually, run:

```bash
curl -fsSL https://cli.zenable.app/install.sh | bash
```

After installing, confirm `command -v zenable` resolves before continuing.

## Instructions

Below are your instructions. The instructions are authoritative — read them carefully and follow them exactly.

!`zenable triage 2>&1 || true`

If the above command failed because the CLI was missing, install it (see Prerequisites) and re-run `zenable triage`.

## Notes

- `zenable triage` auto-detects the PR/MR for the current branch and, by default, returns only unresolved comments from the Zenable AI guardrails bot. Its XML output embeds the instructions to follow for each thread.
- Pass through any arguments the user provides, for example:
  - `zenable triage --all-authors` — include comments from every reviewer, not just the bot.
  - `zenable triage --report-only` — research each comment and print a read-only local report (no commits, pushes, or replies).
  - `zenable triage --pr <n>` / `--mr <n>` — target a specific PR/MR instead of auto-detecting.
- Never force-push while addressing feedback.
