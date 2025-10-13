---
description: Validate code against Zenable requirements before committing
---

# Zenable Validate

Comprehensive validation of your codebase against Zenable conformance requirements. This is useful before committing or pushing changes.

## Usage

```
/validate
```

## What it does

1. Discovers all project files (respecting .gitignore)
2. Runs comprehensive conformance checks across the codebase
3. Validates against:
   - Security policies
   - Quality standards
   - Compliance requirements
   - Organizational best practices
4. Provides a detailed report with severity levels
5. Suggests fixes for any issues found

## When to use

- Before committing significant changes
- Before opening a pull request
- After completing a feature
- During code review preparation
- When onboarding to a new project with Zenable guardrails

## Implementation

**Steps:**

1. Get list of tracked files: `git ls-files`
2. Filter for relevant file types (exclude binaries, build artifacts, etc.)
3. Call `mcp__zenable__check` on all files
4. Aggregate results by severity
5. Present summary with violation counts
6. Offer to fix high-priority issues automatically
