#!/usr/bin/env bash
# Ensure the Zenable CLI is installed. If missing, delegate to the canonical
# installer at cli.zenable.app/install.sh, which verifies the download
# (checksum + signature) and wires up integrations. Best-effort: never blocks.
set -uo pipefail

if command -v zenable >/dev/null 2>&1; then
  exit 0
fi

url="https://cli.zenable.app/install.sh"
echo "[zenable] CLI not found; installing from ${url}..." >&2

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$url" | bash || echo "[zenable] install via curl failed; guardrails hook skipped until 'zenable' is installed." >&2
elif command -v wget >/dev/null 2>&1; then
  wget -qO- "$url" | bash || echo "[zenable] install via wget failed; guardrails hook skipped until 'zenable' is installed." >&2
else
  echo "[zenable] Neither curl nor wget found; install manually: ${url}" >&2
fi

exit 0
