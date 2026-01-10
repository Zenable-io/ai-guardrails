#!/usr/bin/env python3
"""Update version across all plugin configuration files."""

import json
import sys
from pathlib import Path


def update_json_version(file_path: Path, version: str, *keys: str) -> None:
    """Update version in a JSON file at the specified key path.

    Args:
        file_path: Path to the JSON file
        version: New version string
        keys: Path to the version field (e.g., 'plugins', 0, 'version')
    """
    with file_path.open('r') as f:
        data = json.load(f)

    # Navigate to the nested key
    current = data
    for key in keys[:-1]:
        if isinstance(key, int):
            current = current[key]
        else:
            current = current[key]

    # Update the version
    current[keys[-1]] = version

    # Write back with pretty formatting
    with file_path.open('w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

    print(f"Updated {file_path} to version {version}")


def main() -> int:
    """Update versions in all configuration files."""
    if len(sys.argv) != 2:
        print("Usage: update_versions.py <version>")
        return 1

    version = sys.argv[1].lstrip('v')  # Remove 'v' prefix if present
    repo_root = Path(__file__).resolve().parent.parent

    try:
        # Update plugin.json
        plugin_json = repo_root / "plugins/zenable-guardrails/.claude-plugin/plugin.json"
        update_json_version(plugin_json, version, "version")

        # Update marketplace.json - version in plugins array
        marketplace_json = repo_root / ".claude-plugin/marketplace.json"
        update_json_version(marketplace_json, version, "plugins", 0, "version")

        print(f"\n✅ Successfully updated all versions to {version}")
        return 0

    except Exception as e:
        print(f"\n❌ Error updating versions: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
