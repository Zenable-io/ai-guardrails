---
name: feat
description: Implement a new feature with research, a PRD, SOLID design, non-overfitted tests, and incremental commits. Use when the user asks to build, add, or implement a feature, or invokes `/z:feat`.
---

# Feature implementation

We are implementing a new feature. The feature to implement is whatever the user
described when invoking this skill; if that is unclear, ask before writing code.

Do research and ultrathink, write a SOLID, DRY approach. Think through this step by
step and build a PRD and then execute on it.

Add tests for the features but don't overfit them, test the core components and the
base logic of the feature and components, do not test small things like string outputs
and logs or similar unless they are very important.

Find and follow existing design patterns for this in the code base. If you need a new
design pattern, pause and get feedback on the design pattern before proceeding.

Implement the features incrementally, by updating one component, module, or section at
a time and then making sure it tests and works, critiquing and refining it, and then
making a commit successfully with those changes before moving on. If the commit fails,
look at the output and make adjustments as needed; some adjustments may have been
automatically made.
