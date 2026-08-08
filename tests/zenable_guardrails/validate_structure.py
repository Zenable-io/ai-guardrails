#!/usr/bin/env python3
"""Validate the plugin as both a Claude Code plugin and an Agent Plugins 1.0 package.

`plugins/z` ships in two formats from one directory:

- Claude Code reads `.claude-plugin/plugin.json`, `skills/`, and `hooks/hooks.json`.
- Agent Plugins 1.0 clients (Cursor, Codex, VS Code, Kiro, Copilot) read the root
  `plugin.json` and `skills/`. They ignore component types they do not support, so
  `hooks/` and `.claude-plugin/` are inert to them.

Clients that support several formats prefer the client-specific manifest: Codex probes
`.codex-plugin/plugin.json`, then `.claude-plugin/plugin.json`, then
`.cursor-plugin/plugin.json`. Because the Claude manifest wins there, the two manifests
would drift silently -- so the shared metadata is compared field by field below.
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "z"
SCHEMA = Path(__file__).resolve().parent / "schemas" / "agent-plugins-1.0.0-plugin.schema.json"

AGENT_PLUGINS_SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"

# Metadata that describes the same package in both manifests and so must agree.
# `name` is deliberately excluded: Claude Code namespaces commands and skills by plugin
# name (`/z:triage`), while the portable identity is the discoverable `zenable`.
SHARED_FIELDS = ("version", "description", "homepage", "repository", "author", "keywords")

# Agent Skills specification: 1-64 chars, lowercase alphanumeric and hyphens, must not
# start or end with a hyphen, and must not contain consecutive hyphens.
SKILL_NAME_RE = re.compile(r"^(?!.*--)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
MAX_DESCRIPTION = 1024

errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)
    print(f"❌ {msg}")


def ok(msg: str) -> None:
    print(f"✓ {msg}")


def load_json(path: Path, label: str) -> dict | None:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        fail(f"{label}: missing required file {path.relative_to(REPO_ROOT)}")
    except json.JSONDecodeError as exc:
        fail(f"{label}: invalid JSON in {path.relative_to(REPO_ROOT)}: {exc}")
    return None


def validate_against_schema(instance: dict, schema: dict, label: str) -> None:
    """Check `instance` against the subset of JSON Schema the vendored schema uses.

    The Agent Plugins manifest schema is closed and flat, using only type, properties,
    required, additionalProperties, const, pattern, minLength, maxLength, and items --
    so a full JSON Schema implementation would be a dependency for no added coverage.
    """
    for field in schema.get("required", []):
        if field not in instance:
            fail(f"{label}: missing required field `{field}`")

    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        for field in instance:
            if field not in properties:
                fail(f"{label}: unknown top-level field `{field}` (the schema is closed)")

    for field, value in instance.items():
        subschema = properties.get(field)
        if subschema is None:
            continue
        _check_value(value, subschema, f"{label}: `{field}`")


def _check_value(value: object, schema: dict, label: str) -> None:
    expected = schema.get("type")
    types = {
        "string": str,
        "object": dict,
        "array": list,
        "boolean": bool,
        "number": (int, float),
    }
    if expected and not isinstance(value, types[expected]):
        fail(f"{label}: expected {expected}, got {type(value).__name__}")
        return

    if "const" in schema and value != schema["const"]:
        fail(f"{label}: must be {schema['const']!r}, got {value!r}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            fail(f"{label}: shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            fail(f"{label}: longer than {schema['maxLength']} characters")
        if "pattern" in schema and not re.match(schema["pattern"], value):
            fail(f"{label}: {value!r} does not match {schema['pattern']}")

    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _check_value(item, schema["items"], f"{label}[{index}]")

    if isinstance(value, dict) and schema.get("additionalProperties") is False:
        allowed = schema.get("properties", {})
        for key, item in value.items():
            if key not in allowed:
                fail(f"{label}: unknown field `{key}`")
            else:
                _check_value(item, allowed[key], f"{label}.{key}")


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Parse the top-level scalar keys of a SKILL.md YAML frontmatter block."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line or line.startswith((" ", "\t", "#")):
            continue  # nested mapping entry or comment
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def check_claude_package() -> dict | None:
    print("\n== Claude Code package ==")
    manifest = load_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json", "Claude manifest")
    if manifest is None:
        return None
    if "name" not in manifest:
        fail("Claude manifest: missing required `name` field")
    else:
        ok(f"Claude manifest: name `{manifest['name']}`")

    if load_json(PLUGIN_ROOT / "hooks" / "hooks.json", "hooks") is not None:
        ok("hooks/hooks.json is valid JSON")

    bootstrap = PLUGIN_ROOT / "scripts" / "bootstrap.sh"
    if not bootstrap.is_file():
        fail("missing scripts/bootstrap.sh (the SessionStart hook target)")
    else:
        ok("scripts/bootstrap.sh present")

    # Commands were converted to skills so every capability is portable; Agent Plugins
    # 1.0 has no portable home for commands, and Codex only auto-migrates the ones that
    # take no arguments.
    if (PLUGIN_ROOT / "commands").exists():
        fail("commands/ exists: capabilities must be skills so they are portable")
    else:
        ok("no commands/ (all capabilities are portable skills)")
    return manifest


def check_agent_plugin_package() -> dict | None:
    print("\n== Agent Plugins 1.0 package ==")
    manifest = load_json(PLUGIN_ROOT / "plugin.json", "Agent Plugins manifest")
    schema = load_json(SCHEMA, "vendored schema")
    if manifest is None or schema is None:
        return None

    if manifest.get("$schema") != AGENT_PLUGINS_SCHEMA_ID:
        fail(f"Agent Plugins manifest: `$schema` must be {AGENT_PLUGINS_SCHEMA_ID}")

    before = len(errors)
    validate_against_schema(manifest, schema, "Agent Plugins manifest")
    if len(errors) == before:
        ok(f"plugin.json validates against {SCHEMA.name}")
        ok(f"Agent Plugins manifest: name `{manifest['name']}`")
    return manifest


def check_manifests_agree(claude: dict | None, portable: dict | None) -> None:
    print("\n== Manifest sync ==")
    if not claude or not portable:
        return
    drifted = [f for f in SHARED_FIELDS if claude.get(f) != portable.get(f)]
    for field in drifted:
        fail(
            f"manifests disagree on `{field}`: "
            f".claude-plugin={claude.get(field)!r} vs plugin.json={portable.get(field)!r}"
        )
    if not drifted:
        ok(f"shared metadata agrees across both manifests ({', '.join(SHARED_FIELDS)})")


def check_mcp_not_bundled() -> None:
    print("\n== MCP ==")
    # The Zenable MCP server needs a one-time out-of-band login to support CIMD, which
    # `zenable install mcp <ide>` manages. A bundled server entry -- Claude Code
    # auto-discovers a plugin-root `.mcp.json`, and Agent Plugins clients read
    # `mcp.json` -- would leave users configured but unauthorized.
    bundled = [n for n in (".mcp.json", "mcp.json") if (PLUGIN_ROOT / n).is_file()]
    for name in bundled:
        fail(
            f"{name} must not exist: it would auto-install the MCP server, which "
            "needs a user-initiated `zenable install mcp <ide>` login"
        )
    if not bundled:
        ok("no bundled MCP server (CLI-installed, by design)")


def check_marketplaces(version: str | None) -> None:
    """Both marketplace catalogs must resolve to `z@zenable` and the same directory.

    Distribution sits outside the Agent Plugins portable contract, so each client
    brings its own catalog format: Claude Code reads `.claude-plugin/marketplace.json`
    and Codex reads `.agents/plugins/marketplace.json`. The install commands in the
    README only stay correct if both agree.

    Releases hand-bump the version, so it lives in three places: both plugin manifests
    and the Claude marketplace entry. The Codex catalog carries no version -- Codex
    reads it from the plugin itself.
    """
    print("\n== Marketplaces ==")
    catalogs = {
        "claude": REPO_ROOT / ".claude-plugin" / "marketplace.json",
        "agents": REPO_ROOT / ".agents" / "plugins" / "marketplace.json",
    }
    expected_path = f"./{PLUGIN_ROOT.relative_to(REPO_ROOT).as_posix()}"

    for label, path in catalogs.items():
        catalog = load_json(path, f"{label} marketplace")
        if catalog is None:
            continue
        if catalog.get("name") != "zenable":
            fail(f"{label} marketplace: name must be `zenable`, got {catalog.get('name')!r}")

        entries = catalog.get("plugins") or []
        entry = next((e for e in entries if e.get("name") == "z"), None)
        if entry is None:
            fail(f"{label} marketplace: no plugin entry named `z`")
            continue

        source = entry.get("source")
        # Claude Code takes a bare path string; Codex takes {"source", "path"}.
        actual = source.get("path") if isinstance(source, dict) else source
        if actual != expected_path:
            fail(f"{label} marketplace: `z` points at {actual!r}, expected {expected_path!r}")
        else:
            ok(f"{label} marketplace: z@zenable -> {expected_path}")

        if "version" in entry and version is not None and entry["version"] != version:
            fail(
                f"{label} marketplace: `z` is version {entry['version']!r}, but the "
                f"plugin manifests say {version!r}"
            )


def check_skills() -> int:
    print("\n== Skills ==")
    skills_dir = PLUGIN_ROOT / "skills"
    if not skills_dir.is_dir():
        fail("missing required directory: skills/")
        return 0

    count = 0
    for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        count += 1
        manifest = skill / "SKILL.md"
        if not manifest.is_file():
            fail(f"skills/{skill.name}: missing SKILL.md")
            continue

        fields = parse_frontmatter(manifest.read_text())
        if fields is None:
            fail(f"skills/{skill.name}: SKILL.md has no YAML frontmatter block")
            continue

        name = fields.get("name")
        if name is None:
            fail(f"skills/{skill.name}: frontmatter missing `name`")
        elif name != skill.name:
            fail(f"skills/{skill.name}: frontmatter name `{name}` must match directory")
        elif not SKILL_NAME_RE.match(name) or len(name) > 64:
            fail(f"skills/{skill.name}: `{name}` violates Agent Skills naming rules")

        description = fields.get("description")
        if not description:
            fail(f"skills/{skill.name}: frontmatter missing `description`")
        elif len(description) > MAX_DESCRIPTION:
            fail(f"skills/{skill.name}: description exceeds {MAX_DESCRIPTION} characters")

        if name == skill.name and description:
            ok(f"skills/{skill.name}")
    return count


def check_containment() -> None:
    print("\n== Package containment ==")
    escaped = [
        p.relative_to(PLUGIN_ROOT)
        for p in PLUGIN_ROOT.rglob("*")
        if p.is_symlink() and not str(p.resolve()).startswith(str(PLUGIN_ROOT))
    ]
    for path in escaped:
        fail(f"symlink escapes the plugin root: {path}")
    if not escaped:
        ok("every path resolves inside the plugin root")


def main() -> int:
    print(f"Validating {PLUGIN_ROOT.relative_to(REPO_ROOT)} in both formats...")
    claude = check_claude_package()
    portable = check_agent_plugin_package()
    check_manifests_agree(claude, portable)
    check_mcp_not_bundled()
    check_marketplaces((claude or {}).get("version"))
    skill_count = check_skills()
    check_containment()

    print()
    if errors:
        print(f"Validation FAILED with {len(errors)} error(s).")
        return 1

    print(f"Plugin structure validation passed! Portable skills: {skill_count}")
    print()
    print("Claude Code:")
    print("  /plugin marketplace add Zenable-io/ai-guardrails")
    print("  /plugin install z@zenable")
    print("Agent Plugins 1.0 clients (Cursor, Codex, VS Code, Kiro, Copilot):")
    print("  install the `zenable` plugin from this repository")
    return 0


if __name__ == "__main__":
    sys.exit(main())
