---
description: Run Zenable conformance checks and view requirements
---

# Zenable Check

Run conformance checks on files to validate they meet organizational requirements, security standards, and quality guidelines. Can also display active requirements and perform comprehensive validation.

## Usage

```
/check [options] [file-paths...]
```

### Options

- No arguments: Check all modified files in the current git repository
- `--all` or `-a`: Comprehensive validation of entire codebase
- `--requirements` or `-r`: Display active requirements and policies
- `[file-paths...]`: Check specific files or directories

## What it does

1. **File checks** (default or with file paths):
   - Identifies changed or specified files
   - Validates code quality standards
   - Checks security requirements
   - Enforces organizational policies
   - Verifies best practices
   - Reports violations with actionable recommendations

2. **Full validation** (`--all`):
   - Discovers all project files (respecting .gitignore)
   - Runs comprehensive conformance checks across codebase
   - Provides detailed report with severity levels
   - Suggests fixes for issues found

3. **Requirements display** (`--requirements`):
   - Shows active conformance requirements and policies
   - Displays security requirements, quality standards, compliance guardrails
   - Provides context about why each requirement matters
   - Links to detailed documentation

## Examples

```
/check                              # Check modified files
/check src/api/auth.py              # Check specific file
/check --all                        # Validate entire codebase
/check --requirements               # Show active requirements
/check -a src/                      # Validate entire src directory
```

## When to use

- **During development**: Check modified files continuously
- **Before commits**: Validate changes before committing
- **Before PRs**: Run `--all` for comprehensive validation
- **Onboarding**: Use `--requirements` to understand project standards
- **Troubleshooting**: Check specific files after conformance failures

## Implementation

Use the `mcp__zenable__conformance_check` tool (provided by the Zenable MCP server) to run conformance checks.

**Steps:**

1. Parse command arguments to determine mode (check/validate/requirements)
2. For file checks:
   - If no file paths: use `git diff --name-only` to find modified files
   - If `--all`: use `git ls-files` to get all tracked files
3. Call `mcp__zenable__conformance_check` with appropriate parameters
4. Parse and present results to the user
5. If violations found, offer to help fix them
6. For requirements mode, format and display active policies by category
