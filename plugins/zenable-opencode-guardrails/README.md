# 🛡️ Zenable OpenCode Guardrails Plugin

Zenable guardrails plugin for [OpenCode](https://opencode.ai). Automatically reviews each file edit against your requirements — deterministic policy-as-code plus AI review — and feeds any findings back to the agent.

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

The plugin subscribes to OpenCode's `tool.execute.after` hook for file-editing tools (`edit`, `write`, `multiedit`, `apply_patch`) and runs `zenable hook` after each edit to review the change against your guardrails.

On load, the plugin also ensures the Zenable CLI is present: if `zenable` isn't on your `PATH`, it installs it from [cli.zenable.app](https://cli.zenable.app) (the installer verifies the download and wires up integrations). This is a one-time, no-op-once-installed step — you don't need to `curl` anything yourself.

## Requirements

- [OpenCode](https://opencode.ai) installed
- `curl` or `wget` available (used once to fetch the Zenable CLI installer)

The plugin installs the Zenable CLI automatically. To install it ahead of time:

```bash
curl -fsSL https://cli.zenable.app/install.sh | bash
```
