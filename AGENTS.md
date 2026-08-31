# AGENTS.md

## This repository is public

Everything here ships to anyone who installs the plugin, so nothing may name
Zenable's private internals. Do not reference private repository names, internal
file paths, service or module names, internal task/script names, bucket or
infrastructure identifiers, tenant identifiers, or internal ticket links — not
in code, comments, docstrings, error messages, tests, or docs.

This applies to explanations too. When behaviour here is constrained by
something internal, describe the *constraint* and why it exists, not the system
that imposes it: "the versioned filename must stay literal because
asset-retention tooling scans issued reports for it" rather than naming the
scanner, its repo, or its path. A future maintainer needs the invariant; they do
not need — and outside readers must not get — the internal map.

Public identifiers are fine: `zenable.app` URLs, the published MCP server, the
plugin's own paths, and third-party names like `echarts` or `mermaid`.

## Releasing and the plugin version

The plugin version lives in **two** manifests:

- `.claude-plugin/marketplace.json` → `plugins[0].version`
- `plugins/z/.claude-plugin/plugin.json` → `version`

Claude Code reads the version from these manifests, **not** from git tags. If they
disagree with the released tag, `/plugin list` reports the stale manifest value and
`/plugin update` sees no version change to act on.

**Never bump these by hand.** Releases are cut manually by dispatching the Release
workflow (Actions → Release → Run workflow). `semantic-release` derives the next
version from the conventional commits since the last tag (`feat:` → minor, `fix:` →
patch, `!`/`BREAKING CHANGE:` → major), writes it into both manifests and
`pyproject.toml` (`version_toml`/`version_variables` under `[tool.semantic_release]`),
commits the bump with the changelog as `chore(release): {version}`, pushes that commit
to main, and tags it — so the released tag always points at manifests carrying the
released version.

If nothing since the last tag warrants a bump, the dispatch is a no-op; the `force`
input (`patch`/`minor`/`major`) overrides the derived bump when the history
under-represents the change. The push to main works because the workflow authenticates
with a token minted for an internal GitHub App that the branch ruleset's bypass list
exempts — release commits are the only commits that skip a PR.
