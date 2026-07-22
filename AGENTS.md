# AGENTS.md

## Updating the plugin version

The plugin version lives in **two** manifests and both must be changed together:

- `.claude-plugin/marketplace.json` → `plugins[0].version`
- `plugins/z/.claude-plugin/plugin.json` → `version`

Claude Code reads the version from these manifests, **not** from git tags. If they
disagree with the released tag, `/plugin list` reports the stale manifest value and
`/plugin update` sees no version change to act on.

Releases are tag-only: `semantic-release` derives the version from git tags and has
`version_toml`/`version_variables` empty (see the comment above `[tool.semantic_release]`
in `pyproject.toml`), so **it will not write these files for you**. Bumping them is a
manual step in the same PR as the change being released, chosen to match the version the
commit types will produce (`feat:` → minor, `fix:` → patch, `!`/`BREAKING CHANGE:` → major).

A `chore:`-only PR does not trigger a release, so a bump landed on its own will leave the
manifest ahead of the newest tag until the next `feat:`/`fix:` lands.
