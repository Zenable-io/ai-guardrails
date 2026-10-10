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

If the above shows "NOT INSTALLED", ask the user for permission before
installing anything on their machine. If they approve, get the current install
command for their operating system from https://cli.zenable.app (there is one for
macOS/Linux and one for Windows) and run it. Read it from the page each time rather
than from memory: the page is the source of truth, and the installer it points to
verifies the download (checksum + signature). The page fills in its commands with
JavaScript, so if a rendered view of it shows no command, read the raw HTML.

After installing, confirm `command -v zenable` resolves. If the user declines, stop
and explain that this skill needs the CLI.

### Sign-in and plan

zenable access: !`zenable auth can-i get_findings 2>/dev/null; echo "exit code $?"`

This one call confirms the user is signed in **and** their account has an active
trial or paid plan: `get_findings` is a paid-plan tool, so the server answers `yes`
only for trial and paid accounts. If your client didn't run the command above for
you, run it yourself.

Continue only on exit code 0. For any other code, look it up in the
[Zenable CLI reference](https://docs.zenable.io/integrations/zenable/commands), tell the
user what it means and how to fix it, and stop until the check passes.

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
