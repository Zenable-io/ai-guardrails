# Zenable AI Guardrails

Zenable enforces your organization's coding standards — the requirements your
team decided on — against the code AI agents write, as they write it. Teams
adopt AI coding agents at full speed and stay audit-ready, and developers keep
whatever IDE or agent they already use.

You describe a standard once as a plain-English requirement. Zenable enforces it
with a mix of deterministic static analysis and AI review, and records every
finding — a durable account of what was actually checked, not a claim that an
agent looked.

This repository is the home for Zenable's developer-side integrations: the
Claude Code plugin, a GitLab CI/CD component, a pre-commit hook, and drop-in
configuration for every other AI editor. Your requirements travel with you
across all of them.

> **This README is the quick, self-contained tour.** Full product documentation
> lives at **[zenable.app/docs](https://www.zenable.app/docs)** — each section
> below links to the relevant deep dive.

## How it works

- **Requirements** — your standards, written in plain English ("The system
  shall not log secrets"). They're versioned and scoped, so a rule applies only
  where it should — and they cover more than security: functional, performance,
  and product rules run in the same pass.
- **Guardrails** — the automated enforcement Zenable generates for each
  requirement: deterministic static-analysis rules (Semgrep/OpenGrep, and other
  engines) *plus* AI review for the things rules can't catch. The deterministic
  checks are pre-fetched and run locally, so they add effectively no wall-clock
  time and cost no inference.
- **Findings** — every violation, reported on the exact file and line and
  attributed back to the requirement that produced it. The deterministic pass
  doesn't skip or forget, so the result is the evidence an audit asks for.

Enforcement runs in two places:

- **As your AI writes code** — a post-edit hook reviews each change in your
  editor and feeds violations straight back to the coding agent, so it fixes
  them in the same turn.
- **In your pipeline and before commit** — the same review runs in pre-commit,
  in GitLab CI, and as automated reviews on pull/merge requests.

Over time Zenable learns from the signals your team already produces — fixes, PR
activity, agent and human feedback, false positives — and proposes improvements
to the requirements and guardrails themselves. Those proposals are governed by
policies you set, with a human kept in the loop wherever you require one.

Everything authenticates to the hosted platform at
[`mcp.zenable.app`](https://mcp.zenable.app) over OAuth — no long-lived secrets.

Learn more: [How Zenable works](https://www.zenable.app/docs/how-it-works) ·
[Requirements & guardrails](https://www.zenable.app/docs/requirements-and-guardrails)

## Integrations

Each integration below is a self-contained setup. Pick the ones that match your
workflow — they layer cleanly (in-editor + pre-commit + CI is a common combo)
and enforce the same requirements no matter which you use, with nothing to
reconfigure when your team adopts a new tool.

### Claude Code plugin

Install the plugin from this repo's marketplace:

```bash
/plugin marketplace add Zenable-io/ai-guardrails
/plugin install zenable-guardrails@claude-plugins
```

**Team setup** — commit this to `.claude/settings.json` so everyone gets it:

```json
{
  "extraKnownMarketplaces": {
    "claude-plugins": {
      "source": {"source": "github", "repo": "Zenable-io/ai-guardrails"}
    }
  },
  "enabledPlugins": ["zenable-guardrails@claude-plugins"]
}
```

What the plugin wires up:

- **MCP** — a direct connection to [`mcp.zenable.app`](https://mcp.zenable.app)
  (OAuth) that opens the whole Zenable platform to your agent: your requirements,
  guardrails, and findings; agent observability; how your requirements and
  guardrails improve over time; and configuring the platform itself — no web
  browser required.
- **Hooks** — automatic guardrail review after each file edit. Violations are
  returned to the agent to fix in place.
- **Skills** — a *guardrails reviewer* for autonomous, requirement-aware code
  review, and **`/triage`** to address unresolved Zenable review comments on the
  current PR/MR.
- **CLI** — the local engine behind the hooks and skills, running deterministic,
  token-free guardrail checks.

The hooks call the `zenable` CLI directly, so install it once to activate them
(or run `/triage`, which installs it for you):

```bash
curl -fsSL https://cli.zenable.app/install.sh | bash
```

Deep dive: [Claude Code integration](https://www.zenable.app/docs/integrations/mcp/ide/claude-code)

### Other AI editors

The same guardrails — remote MCP plus an automatic post-edit review — work
across Cursor, VS Code, Codex, GitHub Copilot CLI, and many more. Install the
Zenable CLI, then let it write each editor's config:

```bash
curl -fsSL https://cli.zenable.app/install.sh | bash

zenable install cursor      # or: codex, vscode, copilot, amp, auggie,
zenable install codex        # antigravity, kiro, goose, devin-desktop, …
zenable install              # auto-detect every installed editor
```

The CLI writes the MCP server config and, where the editor supports it, the
post-edit hook into that editor's own config files. Add `--project` to scope it
to the current repo or `--dry-run` to preview. Run `zenable install --help` for
the full list of supported editors.

Deep dive: [MCP getting started](https://www.zenable.app/docs/integrations/mcp/getting-started) ·
[Zenable CLI reference](https://www.zenable.app/docs/integrations/zenable/commands)

### Pre-commit

Catch violations before they're committed. Install the Zenable CLI first:

```bash
curl -fsSL https://cli.zenable.app/install.sh | bash
```

Then add the hook to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Zenable-io/ai-guardrails
    rev: v1
    hooks:
      - id: zenable-check
```

Deep dive: [Pre-commit setup](https://www.zenable.app/docs/integrations/pre-commit/getting-started)

### GitLab CI/CD component

Run guardrail checks on every GitLab pipeline. Authenticates to Zenable via
GitLab's native OIDC ID tokens — no long-lived secrets required.

```yaml
# .gitlab-ci.yml
include:
  - component: gitlab.com/zenable/ai-guardrails/check@~latest
    inputs:
      paths: ""              # empty = check files changed on this branch
      base_branch: main
      format: "text,sarif=zenable.sarif"
```

Pin to a specific release for reproducibility:

```yaml
include:
  - component: gitlab.com/zenable/ai-guardrails/check@1.0.0
```

SARIF output is uploaded as a GitLab SAST report. See the
[GitLab CI/CD Catalog](https://gitlab.com/explore/catalog/zenable/ai-guardrails)
for the full input reference, or wire up the
[GitLab merge-request reviewer](https://www.zenable.app/docs/integrations/vcs-reviewers/gitlab)
for automated review comments on every MR.

## Documentation

Everything below redirects to [docs.zenable.io](https://docs.zenable.io):

- [Zenable docs home](https://www.zenable.app/docs)
- [How it works](https://www.zenable.app/docs/how-it-works)
- [Requirements & guardrails](https://www.zenable.app/docs/requirements-and-guardrails)
- [MCP getting started](https://www.zenable.app/docs/integrations/mcp/getting-started)
- [Claude Code integration](https://www.zenable.app/docs/integrations/mcp/ide/claude-code)
- [Pre-commit setup](https://www.zenable.app/docs/integrations/pre-commit/getting-started)
- [GitLab reviewer](https://www.zenable.app/docs/integrations/vcs-reviewers/gitlab) ·
  [GitHub reviewer](https://www.zenable.app/docs/integrations/vcs-reviewers/github)
- [Zenable CLI reference](https://www.zenable.app/docs/integrations/zenable/commands)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, commit
conventions, and release process.

This project uses [Conventional Commits](https://www.conventionalcommits.org/)
and automated semantic versioning.

## Support

- **Issues:** [GitHub Issues](https://github.com/Zenable-io/ai-guardrails/issues)
- **Discussions:** [GitHub Discussions](https://github.com/Zenable-io/ai-guardrails/discussions)
- **Website:** [zenable.io](https://zenable.io)
