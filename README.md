# Zenable AI Guardrails

AI coding guardrails for Claude Code. Enforce organizational standards, security policies, and quality requirements directly in your development workflow.

## Quick Start

```bash
# Add marketplace and install plugin
/plugin marketplace add Zenable-io/ai-guardrails
/plugin install zenable-guardrails@claude-plugins

# Try it out
/check
```

## Team Setup

Add to `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "claude-plugins": {
      "source": {"source": "github", "repo": "Zenable-io/ai-guardrails"}
    }
  },
  "enabledPlugins": ["zenable-guardrails@claude-plugins"]
}
```

## What's Included

**Commands:** `/check`, `/validate`, `/requirements`
**Agent:** Guardrails reviewer for conformance-focused code review
**Hooks:** Automatic validation on file edits and commits
**MCP:** Direct connection to [mcp.zenable.app](https://mcp.zenable.app)

## Usage

```bash
/check                    # Validate changed files
/validate                 # Full codebase validation
/requirements             # Show active policies
```

Or ask the agent:
```
Review my API changes for security compliance
```

## Pre-commit Integration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Zenable-io/ai-guardrails
    rev: v1.0.0
    hooks:
      - id: zenable-check
```


## Documentation

- [Claude Code Integration](https://docs.zenable.io/integrations/mcp/ide/claude-code)
- [MCP Getting Started](https://docs.zenable.io/integrations/mcp/getting-started)
- [Pre-commit Setup](https://docs.zenable.io/integrations/pre-commit/getting-started)
- [Zenable Docs](https://docs.zenable.io)

## Support

**Issues:** [GitHub Issues](https://github.com/Zenable-io/ai-guardrails/issues)
**Website:** [zenable.io](https://zenable.io)

## License

Apache-2.0
