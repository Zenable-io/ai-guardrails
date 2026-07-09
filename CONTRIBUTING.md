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
│   └── marketplace.json          # Marketplace configuration
├── .github/
│   ├── actions/
│   │   └── bootstrap/            # Reusable setup action
│   └── workflows/
│       ├── ci.yml                # CI: lint and test
│       ├── semantic-release.yml  # Automated releases
│       └── update.yml            # Dependency updates
├── plugins/
│   └── zenable-guardrails/
│       ├── .claude-plugin/
│       │   └── plugin.json       # Plugin metadata
│       ├── commands/            # Slash commands (feat, debug, rebase, …)
│       ├── hooks/
│       │   └── hooks.json        # Event hooks
│       ├── scripts/
│       │   └── bootstrap.sh      # SessionStart CLI bootstrap
│       └── skills/
│           ├── guardrails-reviewer/
│           │   └── SKILL.md      # Autonomous conformance reviewer
│           └── triage/
│               └── SKILL.md      # /triage review-comment resolver
├── tests/
│   └── zenable_guardrails/
│       └── validate_structure.py # Plugin validation
├── pyproject.toml                # Project config + semantic-release
├── Taskfile.yml                  # Task automation
└── README.md
```

## Plugin Development

### Adding a New Command

1. Create `plugins/zenable-guardrails/commands/my-command.md`:
   ```markdown
   ---
   description: Brief description of what this command does
   ---

   # My Command

   Detailed explanation and implementation instructions for Claude.
   ```

2. Test locally:
   ```bash
   task test
   ```

### Adding a New Skill

1. Create `plugins/zenable-guardrails/skills/my-skill/SKILL.md`:
   ```yaml
   ---
   name: my-skill
   description: Clear description with trigger keywords. Use when...
   allowed-tools: Read, Write, Edit, Bash
   ---

   # My Skill

   Detailed instructions for autonomous activation.
   ```

2. Update validation test if needed

3. Test that Claude activates it appropriately

### Modifying Hooks

Edit `plugins/zenable-guardrails/hooks/hooks.json`:
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
# Validate structure
task test

# Install in Claude Code (from repo root)
/plugin marketplace add ./
/plugin install zenable-guardrails@zenable-ai-guardrails
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
