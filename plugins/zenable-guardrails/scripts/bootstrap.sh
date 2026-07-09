#!/usr/bin/env sh
# Zenable plugin bootstrap (runs on SessionStart).
#
# The plugin delivers the MCP server, commands, and skills natively. Local
# conformance review, CLI self-update, and usage telemetry all ride the
# `zenable` CLI's OWN hooks, so the plugin's only job here is to make sure the
# CLI is installed and its Claude Code hooks are wired, then get out of the way.
# The CLI -- not the plugin -- owns that hook lifecycle (schema migration,
# autosync, drift telemetry), so a plugin user and a `zenable install` user
# converge on identical config with no duplicate hooks firing.
#
# Contract: idempotent, TTL-gated, fail-soft. It must never block or fail a
# session, so the network work runs in a detached worker and every path exits
# 0 with no stdout (SessionStart stdout is injected into Claude's context).
# Missed work is retried next session -- the timestamp is only stamped on a
# completed worker run.
#
# Runs cross-platform: Claude Code executes hook commands via `sh -c` on
# macOS/Linux and Git Bash on Windows, both of which run this POSIX script.
set -u

# Tag telemetry so plugin-originated installs are distinguishable, and force
# the CLI's non-interactive path (no prompts inside a hook).
ZENABLE_INVOCATION_SOURCE=claude-plugin
ZENABLE_NONINTERACTIVE=1
export ZENABLE_INVOCATION_SOURCE ZENABLE_NONINTERACTIVE

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/zenable"
stamp="$state_dir/plugin-bootstrap"
ttl=43200 # 12h, matching the CLI's own autosync/self-update cadence.

# Detached worker: the actual (slow, network-bound) install work. Split into a
# self-reinvocation so the parent can nohup it and return instantly.
if [ "${1:-}" = "--worker" ]; then
  if command -v zenable >/dev/null 2>&1; then
    # CLI already here: ensure the full Claude Code hook set is wired. Hooks
    # only -- the plugin's own .mcp.json provides the MCP server, so we never
    # `claude mcp add` from here and never race the plugin's MCP entry.
    zenable install hook claude-code >/dev/null 2>&1 || true
  else
    # CLI missing: the canonical installer verifies the download (checksum +
    # signature) and, run non-interactively, auto-configures the detected IDE
    # integrations (Claude Code among them).
    url=https://cli.zenable.app/install.sh
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "$url" | bash >/dev/null 2>&1 || true
    elif command -v wget >/dev/null 2>&1; then
      wget -qO- "$url" | bash >/dev/null 2>&1 || true
    fi
  fi
  mkdir -p "$state_dir" 2>/dev/null && date +%s >"$stamp" 2>/dev/null
  exit 0
fi

# Fast path: CLI present and bootstrapped within the TTL -> nothing to do. Keeps
# steady-state SessionStart cost to a couple of stat/read calls.
if command -v zenable >/dev/null 2>&1 && [ -f "$stamp" ]; then
  now=$(date +%s 2>/dev/null || echo 0)
  last=$(cat "$stamp" 2>/dev/null || echo 0)
  if [ "$now" -gt 0 ] && [ $((now - last)) -lt "$ttl" ]; then
    exit 0
  fi
fi

# Detach the worker so SessionStart returns immediately; never block a session.
nohup "$0" --worker >/dev/null 2>&1 &

exit 0
