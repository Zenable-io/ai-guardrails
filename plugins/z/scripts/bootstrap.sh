#!/usr/bin/env sh
# Zenable plugin bootstrap (SessionStart): install the CLI and wire its hooks.
set -u

ZENABLE_INVOCATION_SOURCE=claude-plugin
ZENABLE_NONINTERACTIVE=1
export ZENABLE_INVOCATION_SOURCE ZENABLE_NONINTERACTIVE

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/zenable"
stamp="$state_dir/plugin-bootstrap"
ttl=43200 # 12h

if [ "${1:-}" = "--worker" ]; then
  # Hooks only. In order to support CIMD, the MCP server needs a one-time
  # interactive login (`zenable install mcp claude-code`) that the user runs
  # themselves, so a non-interactive hook must never install it.
  if command -v zenable >/dev/null 2>&1; then
    zenable install hook claude-code >/dev/null 2>&1 || true
  else
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

if command -v zenable >/dev/null 2>&1 && [ -f "$stamp" ]; then
  now=$(date +%s 2>/dev/null || echo 0)
  last=$(cat "$stamp" 2>/dev/null || echo 0)
  if [ "$now" -gt 0 ] && [ $((now - last)) -lt "$ttl" ]; then
    exit 0
  fi
fi

nohup "$0" --worker >/dev/null 2>&1 &

exit 0
