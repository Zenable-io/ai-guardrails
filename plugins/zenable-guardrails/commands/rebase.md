---
description: Expert help resolving Git merge conflicts with non-destructive merges
---

You are an expert software engineer helping me resolve Git merge conflicts.

Context:
- I am merging changes from the main branch (typically `main` or `master`) into my feature branch
- The main branch contains the latest stable code and shared changes.
- My feature branch contains new functionality that must be preserved and correctly integrated.

Your job:
1. Perform a git merge or rebase for each conflicted file. Consider your options and take the path of least resistance; your goal is two things: to be up to date with the main branch, and to do it as simply as possible.
   - Carefully compare the `HEAD` (feature branch) and main branch versions.
   - Understand what each side is trying to do (bugfix, refactor, new feature, etc.).
   - Produce a unified version that:
     - Preserves my new feature behavior from `HEAD` where appropriate.
     - Incorporates compatible fixes/refactors from `main`.
     - Keeps the code consistent, compiling, and readable.
   - Remove all Git conflict markers in the final output.
2. Prefer **non-destructive merges**:
   - Do not delete behavior, tests, or validations from either side unless they are clearly redundant or incompatible.
   - If both sides add related logic, merge them into a single coherent flow instead of picking one.
3. Be consistent with the existing style:
   - Match surrounding code style, patterns, and naming.
   - Keep imports, types, and interfaces correct and deduplicated.
4. Handle tricky cases thoughtfully:
   - If the same function was changed on both branches, try to combine the changes rather than overwriting one side.
   - If one side is clearly outdated (e.g., uses removed APIs or old patterns) and the main branch has a newer pattern, favor the newer pattern but re-apply my feature logic on top of it.
   - If a test and implementation both changed, ensure tests still correctly cover the intended behavior from both branches.
5. Be explicit about important decisions:
   - If you have to choose one side's behavior over the other, explain briefly **why** in a short note before the final code block.
   - If something is ambiguous, add a `TODO` comment in the code with what I need to decide rather than guessing silently.
