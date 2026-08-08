---
name: prfeedback
description: Address every unresolved pull request comment on the current branch's PR by making code changes or replying, then mark each thread as addressed. Use when the user asks to handle PR feedback or review comments from human reviewers, or invokes `/z:prfeedback`.
---

# Address PR feedback

Retrieve all of the unresolved PR comments on the PR that corresponds to this branch.
Lookup the PR number using `gh pr view --json number -q .number`, and then address each
individual comment one at a time. NEVER FORCE PUSH.

> For unresolved comments left by the **Zenable AI guardrails bot** specifically, use the
> `triage` skill instead — it understands that bot's finding format.

The helper scripts below ship with this skill, in its `scripts/` directory. They are
plain `bash` + `gh`, with no other dependencies.

Before running them, set `SCRIPTS` to that directory — the working directory is the
user's repository, which has no `scripts/` directory of its own:

```bash
# In Claude Code, ${CLAUDE_PLUGIN_ROOT} is substituted for you and this just works.
# In every other client that variable is unset, so fall back to the absolute path of
# the directory containing this SKILL.md, which you already know from loading it.
SCRIPTS="${CLAUDE_PLUGIN_ROOT}/skills/prfeedback/scripts"
[ -x "${SCRIPTS}/dump-unresolved-comments.sh" ] || SCRIPTS="<absolute path of this skill's directory>/scripts"
```

Verify with `ls "${SCRIPTS}"` before continuing; both scripts must be listed.

For each comment, determine if code changes are needed:
- If YES: make changes, commit, push, then mark thread as addressed with commit hash
- If NO: reply to thread with custom comment (no commit needed)

Use the `mark-addressed.sh` script to either:
1. Mark thread as addressed with a commit hash (when code changes were made)
2. Reply to thread with custom comment (for questions, clarifications, acknowledgments, etc.)

MAKE SURE that all comments are addressed completely and independently.

For example:

```console
export PR_NUMBER="$(gh pr view --json number -q .number)"

# 1. Get unresolved threads
"${SCRIPTS}/dump-unresolved-comments.sh" "${PR_NUMBER}"

# 2a. If code changes needed: make changes, commit and push
git add <files>
git commit -m "fix: address feedback from thread"
git push

# 3a. Mark thread as addressed with commit hash (for threads with specific line numbers)
"${SCRIPTS}/mark-addressed.sh" "${PR_NUMBER}" path/to/file.py 118 $(git rev-parse HEAD)

# 3b. For file-level threads (no specific line number), use '-' as the line number
"${SCRIPTS}/mark-addressed.sh" "${PR_NUMBER}" path/to/file.py - $(git rev-parse HEAD)

# 3c. If multiple file-level threads exist, specify which one (1-indexed)
"${SCRIPTS}/mark-addressed.sh" "${PR_NUMBER}" path/to/file.py - $(git rev-parse HEAD) 2

# 2b. If NO code changes needed: reply with custom comment (no commit)
"${SCRIPTS}/mark-addressed.sh" "${PR_NUMBER}" path/to/file.py 118 --comment "This is intentional because we need to maintain backward compatibility"

# Alternative: use -c shorthand for --comment
"${SCRIPTS}/mark-addressed.sh" "${PR_NUMBER}" path/to/file.py - -c "Good catch! However, this behavior is documented in the README"

# For file-level threads with custom comment and specific thread index
"${SCRIPTS}/mark-addressed.sh" "${PR_NUMBER}" path/to/file.py - --comment "Acknowledged, will track in separate issue" 2

# Then address remaining threads, using appropriate method for each
```

At the end of this, re-run the tests to ensure they pass. Use the appropriate test
command for this repository (e.g., `task test`, `npm test`, `pytest`, etc.).

Finally, git add, commit, and push all changes to the remote branch with an appropriate
commit message.
