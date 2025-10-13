# Integration Examples

This directory contains example configuration files for integrating Zenable guardrails into your projects.

## Claude Code Team Setup

Copy `[.claude-settings.json](./.claude-settings.json)` to your project's `.claude/settings.json`:

```bash
mkdir -p .claude
cp examples/.claude-settings.json .claude/settings.json
```

This automatically enables the Zenable plugin for all team members using Claude Code.

## Pre-commit Hook

Copy `[.pre-commit-config.yaml](./.pre-commit-config.yaml)` to your project root:

```bash
cp examples/.pre-commit-config.yaml .pre-commit-config.yaml
```

Then install pre-commit hooks:

```bash
pre-commit install
```

Now Zenable conformance checks will run automatically on every commit.

## Manual MCP Setup

If you want to use the Zenable MCP server directly without the Claude Code plugin, add this to your Claude Code settings:

```json
{
  "mcpServers": {
    "zenable": {
      "type": "http",
      "url": "https://mcp.zenable.app/mcp"
    }
  }
}
```

## Validation

Test your setup:

```bash
# With Claude Code
/check

# With pre-commit
pre-commit run zenable-check --all-files
```
