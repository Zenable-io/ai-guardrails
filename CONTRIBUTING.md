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
   This installs dependencies and sets up the git hooks. We run them with
   [prek](https://github.com/j178/prek), a drop-in replacement for `pre-commit`
   that reads the same `.pre-commit-config.yaml` but resolves hook environments
   substantially faster.

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
│           ├── assessment/       # /z:assessment — setup + validation + reporting
│           │   ├── SKILL.md
│           │   ├── assets/       # HTML report template + workspace rules
│           │   ├── references/   # Evidence-model tool reference
│           │   └── scripts/      # Evidence transforms + bundle builder (+ tests)
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
disappear everywhere else. Claude Code surfaces plugin skills under the same
`/z:<name>` namespace it uses for commands, so a skill loses nothing.

1. Create `plugins/z/skills/my-skill/SKILL.md`:
   ```yaml
   ---
   name: my-skill
   description: Clear description with trigger keywords. Use when..., or invokes `/z:my-skill`.
   allowed-tools: Read, Write, Edit, Bash
   ---

   # My Skill

   Detailed instructions for autonomous activation.
   ```

   The frontmatter `name` must match the directory name, and `description` must
   say both what the skill does and when to use it. Name the slash command as
   `/z:my-skill` — the bare `/my-skill` is not a real command, and advertising it
   sends users somewhere that does not exist.

2. Keep any scripts, references, or assets the skill needs **inside** the skill
   directory — Agent Plugins requires every referenced path to resolve within
   the package.

3. Run `task test`. It validates both manifests, the marketplace catalogs, and
   every skill — frontmatter, naming rules, description length, and the
   `/z:<name>` command each description advertises.

### Changing plugin metadata

`plugins/z/plugin.json` (Agent Plugins) and `plugins/z/.claude-plugin/plugin.json`
(Claude Code) describe the same package and must be edited together — `task test`
fails if any shared field drifts, `name` included.

The name is `z` everywhere — both manifests and both marketplace catalogs. That is
not cosmetic. A client supporting both formats prefers the **portable** manifest,
and Codex additionally requires its `name` to equal the marketplace entry name:

```console
$ codex plugin add z@zenable
Error: plugin.json name `zenable` does not match marketplace plugin name `z`
```

So a portable manifest named anything other than `z` passes every schema check and
still cannot be installed. Claude Code, meanwhile, namespaces skills by its own
manifest's name, which is what makes them `/z:feat` rather than `/zenable:feat`.
Renaming either manifest breaks one client or the other.

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

`task test` is the whole check — it covers everything an external validator would
tell you about the skills and the manifests, so there is nothing extra to install
or run by hand. `task lint` runs the same git hooks CI runs.

## Code Style

- Python: PEP 8 (enforced by the git hooks)
- JSON: 2-space indentation
- YAML: 2-space indentation, explicit start marker (`---`)
- Markdown: Follow [markdownlint](https://github.com/DavidAnson/markdownlint) rules

## Questions?

- **Issues**: [GitHub Issues](https://github.com/Zenable-io/ai-guardrails/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Zenable-io/ai-guardrails/discussions)
- **Website**: [zenable.io](https://zenable.io)
- **Docs**: [docs.zenable.io](https://docs.zenable.io)
