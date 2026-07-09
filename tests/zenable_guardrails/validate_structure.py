#!/usr/bin/env python3
"""Validate plugin structure and schema compliance."""

import json
import sys
from pathlib import Path


def main() -> int:
    """Validate the Zenable plugin structure."""
    # Find plugin root (2 levels up from this script)
    script_path = Path(__file__).resolve()
    plugin_root = script_path.parent.parent.parent / "plugins" / "z"

    print("Validating Zenable plugin structure...")

    # Check required files exist
    required_files = [
        ".claude-plugin/plugin.json",
        "hooks/hooks.json",
    ]

    for file in required_files:
        file_path = plugin_root / file
        if not file_path.is_file():
            print(f"❌ Missing required file: {file}")
            return 1
        print(f"✓ Found: {file}")

    # Claude Code auto-discovers a plugin-root `.mcp.json` and would install the
    # MCP server from it. The MCP server needs a one-time interactive login
    # (`zenable install mcp claude-code`) that the user runs themselves, so it
    # must not be bundled. A live `.mcp.json` must never exist here.
    live_mcp = plugin_root / ".mcp.json"
    if live_mcp.is_file():
        print(
            "❌ .mcp.json must not exist: it would auto-install the MCP server, "
            "which needs a user-initiated `zenable install mcp claude-code` login."
        )
        return 1
    print("✓ No live .mcp.json (MCP server is CLI-installed, by design)")

    # Check required directories exist
    required_dirs = [
        "commands",
        "skills",
        "hooks",
    ]

    for directory in required_dirs:
        dir_path = plugin_root / directory
        if not dir_path.is_dir():
            print(f"❌ Missing required directory: {directory}")
            return 1
        print(f"✓ Found directory: {directory}")

    # Validate JSON files
    json_files = [
        ".claude-plugin/plugin.json",
        "hooks/hooks.json",
    ]

    for json_file in json_files:
        json_path = plugin_root / json_file
        try:
            with json_path.open("r") as f:
                json.load(f)
            print(f"✓ Valid JSON: {json_file}")
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {json_file}: {e}")
            return 1
        except Exception as e:
            print(f"❌ Error reading {json_file}: {e}")
            return 1

    # Check plugin.json has required fields
    plugin_json_path = plugin_root / ".claude-plugin" / "plugin.json"
    try:
        with plugin_json_path.open("r") as f:
            plugin_data = json.load(f)
        if "name" not in plugin_data:
            print("❌ plugin.json missing required 'name' field")
            return 1
    except Exception as e:
        print(f"❌ Error validating plugin.json fields: {e}")
        return 1

    # Count commands and skills
    commands_dir = plugin_root / "commands"
    skills_dir = plugin_root / "skills"

    command_count = len(list(commands_dir.glob("*.md"))) if commands_dir.exists() else 0
    # Skills are in subdirectories with SKILL.md files
    skill_count = len(list(skills_dir.glob("*/SKILL.md"))) if skills_dir.exists() else 0

    print()
    print("Plugin structure validation passed!")
    print(f"  Commands: {command_count}")
    print(f"  Skills: {skill_count}")
    print()
    print("You can now install this plugin with:")
    print("  /plugin marketplace add Zenable-io/ai-guardrails")
    print("  /plugin install z@zenable")

    return 0


if __name__ == "__main__":
    sys.exit(main())
