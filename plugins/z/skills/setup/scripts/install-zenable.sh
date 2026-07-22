#!/usr/bin/env bash
# Ensure the Zenable CLI is installed. If missing, delegate to the canonical
# installer at cli.zenable.app/install.sh, which verifies the download
# (checksum + signature) and wires up integrations. Best-effort: never blocks.
set -uo pipefail

if command -v zenable >/dev/null 2>&1; then
  echo "[zenable] CLI already installed at $(command -v zenable)"
  exit 0
fi

url="https://cli.zenable.app/install.sh"
echo "[zenable] CLI not found; installing from ${url}..." >&2

# Download to a temp file before executing. Piping the installer straight into
# bash means a mid-stream network failure leaves bash running a truncated
# script; downloading first makes the fetch succeed-or-fail atomically, so a
# partial transfer is never executed.
tmp="$(mktemp)" || {
  echo "[zenable] could not create a temp file; install manually: ${url}" >&2
  exit 0
}
trap 'rm -f "$tmp"' EXIT

downloaded=false
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$url" -o "$tmp" && downloaded=true
elif command -v wget >/dev/null 2>&1; then
  wget -qO "$tmp" "$url" && downloaded=true
else
  echo "[zenable] Neither curl nor wget found; install manually: ${url}" >&2
  exit 0
fi

if [ "$downloaded" != true ] || [ ! -s "$tmp" ]; then
  echo "[zenable] download failed or was incomplete; run 'curl -fsSL ${url} | bash' manually." >&2
  exit 0
fi

bash "$tmp" || echo "[zenable] installer failed; run 'curl -fsSL ${url} | bash' manually." >&2

exit 0
