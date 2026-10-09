---
name: triage
description: Fetch and address unresolved Zenable AI guardrails review comments on the current pull request (GitHub PR) or merge request (GitLab MR). Use this skill whenever the user says "triage", "address PR feedback", "fix review comments", "respond to the guardrails bot", or anything about responding to automated code review feedback on a pull/merge request. Also trigger when the user invokes `/z:triage`.
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
---

# Triage

Address unresolved review comments from the Zenable AI guardrails bot on the pull request (GitHub) or merge request (GitLab) for the current branch.

## Prerequisites

This skill requires the Zenable CLI. Check whether it's installed:

zenable CLI location: !`command -v zenable 2>/dev/null || echo "NOT INSTALLED"`

If the above shows "NOT INSTALLED", install it by running this skill's bundled
installer (idempotent — a no-op once the CLI is present). In Claude Code the variable
below is substituted for you; in every other client it is unset, so fall back to the
absolute path of the directory containing this SKILL.md, which you already know from
loading it:

```bash
INSTALLER="${CLAUDE_PLUGIN_ROOT}/skills/triage/scripts/install-zenable.sh"
[ -f "$INSTALLER" ] || INSTALLER="<absolute path of this skill's directory>/scripts/install-zenable.sh"
bash "$INSTALLER"
```

The script delegates to the canonical installer at
[cli.zenable.app/install.sh](https://cli.zenable.app), which verifies the
download (checksum + signature) before installing. It needs `curl` or `wget`.
If you'd rather install manually, run:

```bash
curl -fsSL https://cli.zenable.app/install.sh | bash
```

After installing, confirm `command -v zenable` resolves before continuing.

### Sign-in and plan

zenable access: !`zenable auth can-i get_findings 2>/dev/null; echo "exit code $?"`

This one call confirms the user is signed in **and** their account has an active
trial or paid plan: `get_findings` is a paid-plan tool, so the server answers `yes`
only for trial and paid accounts. If your client didn't run the command above for
you, run it yourself. Then act on the exit code:

- **0** (`yes`) — ready; continue.
- **21** — not signed in. Ask the user to run `zenable login` in a separate
  terminal, then re-run the check.
- **1** with `no` — signed in, but there's no active trial or paid plan. Stop and
  point the user to https://www.zenable.io/pricing to start a trial or upgrade.
- **1** with nothing else printed — the account isn't fully set up. Stop and ask
  the user to sign in at https://www.zenable.app to finish setting it up.
- **127** — the CLI isn't installed or isn't on `PATH`; go back to the install step.

Do not continue until this check passes.

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
