# 🛡️ Zenable OpenCode Guardrails Plugin

Zenable conformance checking plugin for [OpenCode](https://opencode.ai). Automatically runs conformance checks after file edits.

## Installation

### Quick Install

```bash
zenable install opencode
```

### Manual Install

Add to your `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "zenable": {
      "type": "remote",
      "url": "https://mcp.zenable.app/"
    }
  },
  "plugin": ["@zenable-io/opencode-guardrails"]
}
```

## How It Works

The plugin subscribes to OpenCode's `tool.execute.after` hook for file-editing tools (`edit`, `write`, `multiedit`, `apply_patch`) and runs `zenable hook` after each edit to check conformance.

## Requirements

- [OpenCode](https://opencode.ai) installed
- The Zenable CLI installed and on your `PATH`:

  ```bash
  curl -fsSL https://cli.zenable.app/install.sh | bash
  ```
