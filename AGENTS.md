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
under-represents the change. The push to main works because the workflow pushes over
SSH as the ZenableAutomation machine user, which the branch ruleset's bypass list
exempts — release commits are the only commits that skip a PR.

<!-- zenable:managed start — managed by `zenable`; `zenable uninstall` removes this block -->
This IDE has no Zenable MCP server. To work with Zenable requirements, guardrails, scopes, and findings, shell out to the `zenable api` CLI (it reuses your existing `zenable login`):

- To list your requirements: `zenable api requirements list`
- To list active guardrails: `zenable api guardrails list`
- To list scope definitions: `zenable api requirements list-scope-definitions`
- To list authorable scope types and integration values: `zenable api requirements list-scope-definitions-authoring-options`
- To list detailed findings: `zenable api findings list`
- To read agent triage feedback on a governance object: `zenable api agent-feedback list`
- To read human ratings of a requirement: `zenable api requirements list-feedback`
- To create a new requirement: `zenable api requirements create`
- To create a scope definition: `zenable api requirements create-scope-definitions`
- To update a requirement your tenant owns: `zenable api requirements update`
- To override or publish a marketplace requirement: `zenable api requirements update`

Requirements come in two kinds. Requirements your tenant owns are yours to edit: `zenable api requirements update` changes one in place or publishes a new version of it. Marketplace requirements are published by Zenable and shared across tenants, so they are never edited directly — the same `zenable api requirements update` on a marketplace requirement instead records an override for your tenant (enable/disable it or pin a version), and publishing a new marketplace version requires the marketplace:publish permission.

Run `zenable api <group> <command> --help` for the available flags.
These have no CLI equivalent — use the Zenable dashboard instead: regenerate a guardrail, reinstate a prior guardrail version, restore a soft-deleted requirement.
<!-- zenable:managed end -->
