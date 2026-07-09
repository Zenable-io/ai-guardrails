#!/usr/bin/env bash
# Pin the pre-commit usage example in README.md to this repo's latest major tag
# (v1, v2, ...). Run by `task update`, so a v2.0.0 release flips the example from
# v1 to v2 on the next update; v1.x.y patch tags never move it.
set -Eeuo pipefail

readme="$(git rev-parse --show-toplevel)/README.md"

# Biggest bare major tag (v1, v2, ... v10) on origin — ignores full vX.Y.Z tags.
latest="$(git ls-remote --tags --refs origin \
  | grep -oE 'v[0-9]+$' \
  | sort -V \
  | tail -1)"

if [ -z "${latest}" ]; then
  echo "No vN major tags found on origin" >&2
  exit 1
fi

sed -i.bak -E "s|(rev: )v[0-9][0-9.]*|\1${latest}|" "${readme}"
rm -f "${readme}.bak"
echo "Pinned README pre-commit rev to ${latest}"
