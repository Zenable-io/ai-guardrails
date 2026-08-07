# Contributing to Zenable AI Guardrails

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Zenable-io/ai-guardrails.git
   cd ai-guardrails
   ```

2. **Initialize the development environment**:
   ```bash
   task init
   ```
   This installs dependencies and sets up pre-commit hooks.

3. **Run tests**:
   ```bash
   task test
   ```

4. **Run linters**:
   ```bash
   task lint
   ```

## Making Changes

### Commit Message Format

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automated semantic versioning.

**Format**: `<type>(<scope>): <description>`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `build`: Build system or dependency changes
- `ci`: CI configuration changes
- `chore`: Other changes

**Breaking Changes**: Add `BREAKING CHANGE:` in the commit body or add `!` after type to trigger major version bump:
```
feat!: remove support for Python 3.12

BREAKING CHANGE: Minimum Python version is now 3.13
```

**Examples**:
```bash
feat(plugin): add new conformance check for API security
fix(hooks): correct version pinning syntax for uvx
docs(readme): update installation instructions
chore(deps): update pre-commit hooks
```

### Pull Request Process

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/my-new-feature
   ```

2. Make your changes following the code style

3. Ensure tests pass:
   ```bash
   task test
   ```

4. Commit using conventional commit format

5. Push and create a pull request to `main`

6. Wait for CI checks to pass and review

## Project Structure

```
ai-guardrails/
├── .claude-plugin/
│   └── marketplace.json          # Marketplace catalog (Claude Code)
├── .agents/
│   └── plugins/
│       └── marketplace.json      # Marketplace catalog (Codex)
├── .github/
│   ├── actions/
│   │   └── bootstrap/            # Reusable setup action
│   └── workflows/
│       ├── ci.yml                # CI: lint and test
│       ├── semantic-release.yml  # Automated releases
│       └── update.yml            # Dependency updates
├── plugins/
│   └── z/                        # One directory, two plugin formats
│       ├── plugin.json           # Agent Plugins 1.0 manifest (portable)
│       ├── .claude-plugin/
│       │   └── plugin.json       # Claude Code manifest
│       ├── hooks/                # Claude Code only — not portable
│       │   └── hooks.json        # Event hooks
│       ├── scripts/
│       │   └── bootstrap.sh      # SessionStart CLI bootstrap
│       └── skills/               # Shared by BOTH formats
│           ├── guardrails-reviewer/
│           │   └── SKILL.md      # Autonomous conformance reviewer
│           ├── setup/            # /z:setup onboarding
│           ├── triage/           # /z:triage review-comment resolver
│           └── …                 # feat, debug, addtests, doublecheck,
│                                 # rebase, prfeedback, researchbranch
├── tests/
│   └── zenable_guardrails/
│       ├── schemas/              # Vendored upstream Agent Plugins schema
│       └── validate_structure.py # Validates both formats + drift
├── pyproject.toml                # Project config + semantic-release
├── Taskfile.yml                  # Task automation
└── README.md
```

## Plugin Development

### Adding a New Capability

Every capability is a **skill**. Don't add slash commands: Agent Plugins 1.0 has
no portable home for them, so a command would work in Claude Code and silently
disappear in Cursor, Codex, VS Code, Kiro, and Copilot. Claude Code surfaces
plugin skills under the same `/z:<name>` namespace it uses for commands, so a
skill loses nothing.

1. Create `plugins/z/skills/my-skill/SKILL.md`:
   ```yaml
   ---
   name: my-skill
   description: Clear description with trigger keywords. Use when...
   allowed-tools: Read, Write, Edit, Bash
   ---

   # My Skill

   Detailed instructions for autonomous activation.
   ```

   The frontmatter `name` must match the directory name, and `description` must
   say both what the skill does and when to use it.

2. Keep any scripts, references, or assets the skill needs **inside** the skill
   directory — Agent Plugins requires every referenced path to resolve within
   the package.

3. Run `task test`, then confirm the skill activates in Claude Code and in at
   least one Agent Plugins client.

### Changing plugin metadata

`plugins/z/plugin.json` (Agent Plugins) and `plugins/z/.claude-plugin/plugin.json`
(Claude Code) describe the same package and must be edited together — `task test`
fails if their shared metadata drifts. The `name` fields differ on purpose: `z`
keeps Claude Code's `/z:` namespace, while `zenable` is the discoverable identity
in shared marketplaces.

This matters because clients that support several formats prefer the
client-specific manifest. Codex, for example, probes `.codex-plugin/plugin.json`,
then `.claude-plugin/plugin.json`, then `.cursor-plugin/plugin.json` — so a stale
Claude manifest would win there and the drift would be invisible.

### Modifying Hooks

Edit `plugins/z/hooks/hooks.json`:
```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "your command here"
      }]
    }]
  }
}
```

## Testing Locally

### Testing the Plugin

```bash
# Validate both formats, manifest drift, and every skill
task test

# Install in Claude Code (from repo root)
/plugin marketplace add ./
/plugin install z@zenable
```

Test the portable format against a real Agent Plugins client too. Codex takes a
local marketplace path, so it round-trips straight from a working tree:

```bash
codex plugin marketplace add .
codex plugin add z@zenable
codex plugin list --json          # confirm it installed

# ...and to undo it
codex plugin remove z@zenable
codex plugin marketplace remove zenable
```

Cursor loads plugins from `~/.cursor/plugins/local/<name>`, so copying or
symlinking `plugins/z` there works for local development.

Upstream validators are worth running when changing skills or the manifest:

```bash
# Agent Skills conformance, from github.com/agentskills/agentskills
skills-ref validate plugins/z/skills/<name>
```

## Code Style

- Python: PEP 8 (enforced by pre-commit)
- JSON: 2-space indentation
- YAML: 2-space indentation, explicit start marker (`---`)
- Markdown: Follow [markdownlint](https://github.com/DavidAnson/markdownlint) rules

## Questions?

- **Issues**: [GitHub Issues](https://github.com/Zenable-io/ai-guardrails/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Zenable-io/ai-guardrails/discussions)
- **Website**: [zenable.io](https://zenable.io)
- **Docs**: [docs.zenable.io](https://docs.zenable.io)
