---
description: Address all unresolved PR comments by making code changes or replying appropriately
---

Retrieve all of the unresolved PR comments on the PR that corresponds to this branch. Lookup the PR number using `gh pr view --json number -q .number`, and then address each individual comment one at a time. NEVER FORCE PUSH.

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
./scripts/dump-unresolved-comments.sh "${PR_NUMBER}"

# 2a. If code changes needed: make changes, commit and push
git add <files>
git commit -m "fix: address feedback from thread"
git push

# 3a. Mark thread as addressed with commit hash (for threads with specific line numbers)
./scripts/mark-addressed.sh "${PR_NUMBER}" path/to/file.py 118 $(git rev-parse HEAD)

# 3b. For file-level threads (no specific line number), use '-' as the line number
./scripts/mark-addressed.sh "${PR_NUMBER}" path/to/file.py - $(git rev-parse HEAD)

# 3c. If multiple file-level threads exist, specify which one (1-indexed)
./scripts/mark-addressed.sh "${PR_NUMBER}" path/to/file.py - $(git rev-parse HEAD) 2

# 2b. If NO code changes needed: reply with custom comment (no commit)
./scripts/mark-addressed.sh "${PR_NUMBER}" path/to/file.py 118 --comment "This is intentional because we need to maintain backward compatibility"

# Alternative: use -c shorthand for --comment
./scripts/mark-addressed.sh "${PR_NUMBER}" path/to/file.py - -c "Good catch! However, this behavior is documented in the README"

# For file-level threads with custom comment and specific thread index
./scripts/mark-addressed.sh "${PR_NUMBER}" path/to/file.py - --comment "Acknowledged, will track in separate issue" 2

# Then address remaining threads, using appropriate method for each
```

At the end of this, re-run the tests to ensure they pass. Use the appropriate test command for this repository (e.g., `task test`, `npm test`, `pytest`, etc.).

Finally, git add, commit, and push all changes to the remote branch with an appropriate commit message.

$ARGUMENTS
