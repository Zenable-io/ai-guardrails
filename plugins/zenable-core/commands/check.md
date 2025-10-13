---
description: Run Zenable conformance checks on changed files or specific paths
---

# Zenable Check

Run conformance checks on files to validate they meet organizational requirements, security standards, and quality guidelines.

## Usage

```
/check [file-paths...]
```

If no file paths are provided, checks all modified files in the current git repository.

## What it does

1. Identifies changed or specified files
2. Calls the Zenable MCP server's `check` tool to validate:
   - Code quality standards
   - Security requirements
   - Organizational policies
   - Best practices
3. Reports any violations with actionable recommendations

## Example

```
/check src/api/auth.py
```

or simply:

```
/check
```

## Implementation

Use the `mcp__zenable__check` tool (provided by the Zenable MCP server) to run conformance checks on the target files.

**Steps:**

1. If no file paths provided: use `git diff --name-only` to find modified files
2. Call `mcp__zenable__check` with the file paths
3. Parse and present the results to the user
4. If violations found, offer to help fix them
