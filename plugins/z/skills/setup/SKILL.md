---
name: setup
description: Guided Zenable onboarding — discover the standards a codebase already has written down, mine them into candidate requirements, triage them with the user, and persist the survivors as scoped Zenable requirements through the Zenable MCP. Use this skill whenever the user wants to onboard a codebase onto Zenable, set up custom requirements/guardrails for a project, or invokes `/z:setup`. Also trigger for phrases like "onboard this repo to Zenable", "set up Zenable requirements for this codebase", or "get Zenable guardrails going here".
---

# Zenable setup

A guided workflow for onboarding a codebase onto Zenable. The goal is a set of durable, well-scoped requirements that reflect how this team actually builds — not a generic checklist.

The key insight: most teams have already written their standards down. They live in ADRs, style guides, rules files, postmortems, and linter configs. Your job is to find that material, turn it into candidate requirements, and let the user cut it down — not to interview them from a blank page about things they've already documented.

Assume you're running unattended for a developer in their own repo. They may not know what the company standard says, what was promised contractually, or who owns what. Design every question so "I don't know" is a fine answer.

## Mental model

Two phases:

1. **Gather Context** — collect what's already written, mine it into candidates, triage with the user
2. **Onboard** — co-author the survivors into precise requirements, scope them, persist them

Phase 1 is where the value is. A strawman built from the user's own ADRs lands very differently than one built from a generic category list.

## Pre-flight

Before any collection work, verify the environment and tell the user what you found.

### zenable CLI

zenable CLI location: !`which zenable 2>/dev/null || echo "NOT INSTALLED"`

zenable CLI version: !`zenable version 2>/dev/null || echo "unavailable"`

If the location above shows "NOT INSTALLED", ask the user for permission before
installing anything on their machine. If they approve, install it:

```bash
bash <skill-path>/scripts/install-zenable.sh
```

After install completes, re-run `zenable version` to confirm. Do not proceed until
the CLI is on PATH. If the user declines installation, stop and explain that this
skill needs the CLI for durable Zenable requirements support.

### Authentication

zenable auth identity: !`zenable auth whoami 2>&1 || echo "NOT AUTHENTICATED"`

If the above shows "NOT AUTHENTICATED" (or any error), ask the user to run `zenable login` in a separate terminal, then re-check. Do not proceed unauthenticated.

### Zenable MCP

Confirm the Zenable MCP tools are available. In Claude Code these surface as `mcp__zenable__*`; in other IDEs they appear under whatever prefix that IDE uses.

If they're absent, ask the user for permission before installing the MCP server.
If they approve, install it via the zenable CLI. The IDE slug for Claude Code is
`claude-code`:

```bash
zenable install mcp claude-code --project
```

If you're running in a different IDE, list the supported slugs and pick the one matching your environment:

```bash
zenable install mcp -h
```

ONLY stop and ask the user for help if your IDE isn't in that list — we cannot fall back to a local-only mode, because without persistent scopes and requirements most of the workflow's value is gone.

If you had to install the MCP server, the user must authenticate to it manually, so tell them. In Claude Code that means sending `/mcp`, selecting `zenable`, and finishing authentication. Other IDEs are similar.

### Resolve the repository identity

Do this now, not at requirement-creation time. Requirements are scoped to repositories, and discovering at the end that the repo doesn't resolve means dozens of failed creates and a confused user.

Repo remote: !`git remote get-url origin 2>/dev/null || echo "NO REMOTE"`

Ask the Zenable MCP whether this repository is known to the tenant. If it resolves, note the identifier for Phase 2. If it does not resolve — or there's no remote at all — settle the fallback now while it's a single decision:

- Ask the user for the correct repository identifier, if they know it
- If they don't, note that scoping will fall back to whatever other dimensions apply, and flag in `requirements.md` that repo scoping is unresolved

### Workspace

Establish a workspace inside the target repo (or cwd if there is no repo). Default location: `./zenable-setup/<UTC-timestamp>/`. Confirm the location with the user before creating it.

**Working note filenames:**

- `sources.md` — what was discovered or provided, where each came from, and what couldn't be reached
- `candidates.md` — the mined candidate pool, clustered, with triage outcomes including what was cut and why
- `context.md` — codebase and engagement context that isn't a requirement itself
- `requirements.md` — final adopted requirements with Zenable IDs and the scopes applied to each
- `simulated-calls.md` — only when the Zenable MCP/CLI aren't available; an explicit log of what would have been called, with synthesized responses marked as such

If you find yourself collapsing these into one file, you've lost the audit trail. Keep them separate.

## Phase 1 — Gather Context

### Step 1: Collect

**Explain, then ask, then look.** Don't open by asking the user what documents they have — a developer working alone will shrug at that question. But don't go reading through their repo unannounced either. Say what you'd like to search for and why, get an explicit go-ahead, and let them narrow it first:

> "I'd like to look through the repo for places your standards are already written down — rules files, ADRs, contributor docs, linter and CI config, CODEOWNERS. That's usually where most of the requirements already live. Anything you'd rather I skip?"

Asking also gives them a natural opening to scope the search before you spend effort on it — "ignore `docs/`, it's all stale" saves both of you a triage pass later. If they'd rather point you at specific files instead of having you search, do it their way.

Once they've agreed, search for:

- **Rules files** — `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.github/copilot-instructions.md`, `.windsurfrules`, and equivalents
- **Decision records** — `docs/adr/`, `docs/decisions/`, `adr/`, or any directory of numbered decision docs
- **Contributor and style guidance** — `CONTRIBUTING.md`, `SECURITY.md`, style guides anywhere under `docs/`
- **Ownership** — `CODEOWNERS` (repo root, `.github/`, or `docs/`). This is a path-to-team map and a direct scoping input; grab it even though it isn't a requirements document.
- **Linter and formatter config** — `ruff.toml`, `pyproject.toml`, `.eslintrc*`, `biome.json`, `.golangci.yml`, `rustfmt.toml`, `.editorconfig`
- **Static analysis config** — `.semgrep/`, `semgrep.yml`, `.bandit`, `sonar-project.properties`
- **CI and hooks** — `.github/workflows/`, `.gitlab-ci.yml`, `.circleci/`, `.pre-commit-config.yaml`
- **Package manifests** — to establish the stack and language mix
- **Operational commitments** — SLO definitions in monitoring config or `docs/`, runbooks, threat models
- **Design and product docs** — anything under `docs/` that reads as a spec, RFC, or PRD

The linter, static-analysis, CI, and hook configs are not requirement sources — they are the **already-enforced** list, and you'll use them in Step 2 to filter candidates. Collect them for that purpose.

**Then ask what's missing**, ordered by whether the user can realistically reach it in one sitting:

- **Reachable now** — anything else on disk, or a public URL you can fetch: engineering blog posts about how they build, public docs, a trust center page
- **Needs pasting or export** — Confluence, Notion, Google Docs, internal wikis
- **Probably out of reach solo** — customer contracts, DPAs, security addenda, SLAs, pentest reports, prior audit findings. Mention these once as high-value if they happen to have them; do not chase them. A developer is not going to get the MSA from legal today.

Record everything found or provided in `sources.md`, including what was named but unreachable — that's a useful list for a later session.

**If the repo has almost nothing** — no rules files, no ADRs, no docs — say so plainly and fall back to interviewing from the generic categories in Step 3. This is a normal outcome, not a failure. It just means Phase 1 is shorter and the strawman is less bespoke.

Let depth control collection effort:

- **Fast** — in-repo auto-discovery only; no document hunting
- **Balanced** — plus anything else the user can point at on disk
- **Exhaustive** — plus public URL fetching, PR review comment history, and the conflict-reconciliation pass in Step 3

### Step 2: Mine

**Extract wholesale.** Go through each collected source and pull out every candidate requirement it contains — not a summary, not the highlights. A written standard may yield forty candidates; that's expected. Filtering happens next, mechanically, before the user sees anything.

For each candidate, record the source and a specific pointer (file, section, line, or quote). That provenance rides along into Phase 2 — a requirement citing the team's own ADR-014 is far more defensible to the developer who trips over it than one citing nothing.

Then filter, in this order:

1. **Dedupe across sources.** The same rule commonly appears in the standard, the CLAUDE.md, and an ADR. Merge them — but **count the corroboration and keep every source pointer**. A rule written down in three places is one the organization genuinely believes, and it should sort near the top of triage rather than collapsing into a single arbitrary citation.
2. **Drop what's already enforced.** Check each candidate against the linter, static-analysis, CI, and pre-commit configs collected in Step 1. If `ruff` already fails the build on it, a Zenable requirement adds noise, not coverage. This filter does a lot of work — it answers the enforced-versus-aspirational question automatically instead of asking the user about it dozens of times.
3. **Drop what doesn't apply to the stack.** A Java convention in a Python repo, a rule for a framework they don't use.

Note the counts at each stage in `candidates.md` so the reduction is auditable.

**Then cluster the survivors.** Clusters exist purely to let a human cut in batches — they are never persisted to Zenable and have no relationship to scopes. Build two groupings:

- **By source** — "18 from the security standard, 9 from ADRs, 6 from CLAUDE.md"
- **By theme** — secrets handling, authorization, error handling, type discipline, testing, and so on

**Label every cluster with the shared claim, not the category noun.** "Error handling (9)" cannot be decided without drilling in. "Error handling at service boundaries — never swallow, always log with context (9)" can be decided from the label alone. Lazy labels quietly defeat the entire point of clustering.

Order clusters by authority and corroboration, strongest first. If the user runs out of patience halfway, the load-bearing material should already be settled.

### Step 3: Interview

Now spend the user's attention on what documents cannot answer.

**Triage pass 1 — cut by source.** Present the source groupings. The single most efficient move available is "that standard is three years stale, drop all of it" — one decision instead of eighteen. Staleness and authority are properties of the document, not of individual rules, so handle them here. Ask which sources are still true, and which have been superseded or quietly abandoned.

**Triage pass 2 — cut by theme.** Present the thematic clusters over whatever survived pass 1. For each: keep, drop, or drill in. Always offer "show me these" and "accept except #4" — clusters are rarely uniformly good or bad, and a blanket accept will eventually bury something they'd have cut.

Record every cut in `candidates.md` with a one-line reason. Dropped is not deleted; a considered-and-rejected list is useful in a later session and costs nothing to keep.

**Then the questions only they can answer:**

- **Conflicts.** Where sources disagree with each other, or with the code as written: "ADR-014 says X, but the code consistently does Y — which is right?" Either answer produces a good requirement, and the question itself is often the most valuable moment in the session.
- **What has actually gone wrong.** Incidents, near-misses, the outage everyone remembers. And specifically: *what review comment do you find yourself leaving over and over?* A rule a human is already enforcing by hand every week is the single best automation candidate available.
- **What's missing.** Now the generic categories earn their keep — as gap-fill over a list the user has already shaped, not as the opening move. Cover security, operational concerns, code quality, and anything domain-specific the codebase suggests.
- **Product and business-logic rules.** Ask for these explicitly. Requirements are not only about security — design patterns, product decisions, performance budgets, and deliberate tradeoffs all belong. Users will self-censor toward security unless invited otherwise.
- **Scope boundaries.** Does this cover the whole repo, or one package inside a monorepo? Which directories are in play, and is anything explicitly out of scope?
- **Roadmap.** Mid-migration, or planning one? This affects requirement durability, and it opens a valuable class of rule: enforcing migration direction, so new code stops using the pattern being retired.

Record codebase and engagement context in `context.md`. Where the user doesn't know — what the official standard says, what was promised contractually, who owns a subsystem — record it as unknown and move on. Do not force an answer, and flag any requirement resting on an uncertain premise so it can be revisited.

## Phase 2 — Onboard

Every surviving candidate becomes its own Zenable requirement. Clusters do not carry over.

### Co-author each requirement

Walk the survivors one at a time. For each, settle:

1. **Title** — short noun phrase, e.g. "Secrets are loaded from environment or secret manager, never hardcoded"
2. **Why it matters here** — grounded in the source it came from or the Phase 1 discussion
3. **What compliant looks like** — concrete, with examples of passing and failing code
4. **Source** — the provenance captured during mining

Draft first, then ask "good? change?". Do not silently finalize a batch and ask for blanket approval.

### Scope each requirement

Scoping is per requirement, not per engagement. A secrets rule may cover everything; a React hooks rule covers one directory and one file type.

**Ask the MCP which scope dimensions it supports** rather than assuming a fixed list — the available dimensions change, and a hardcoded list here will go stale.

Guidance:

- **Almost always include a repository scope**, using the identifier resolved during pre-flight.
- **Add every other dimension that genuinely applies** — file extensions, paths or directories, owning people or teams, and whatever else the MCP exposes. Most of this is inferable rather than worth asking about: a Pydantic rule scopes to `.py`, a frontend rule scopes to the frontend directory, and `CODEOWNERS` supplies the path-to-team mapping. Propose the inference and confirm it; don't interrogate.
- **A repository-only scope is perfectly fine** when nothing else applies.
- **Global scope is allowed but strongly discouraged during initial onboarding.** Never create one without stating why no narrower scope was available, and record that reason in `requirements.md`. If you cannot articulate the reason, you have not looked hard enough for a narrower scope.

Confirm scopes in batches rather than one at a time — reuse the thematic grouping from Step 2 as a presentation device ("these 12 secret rules → this repo, all files; these 6 style rules → this repo, `*.py` — look right?"), and drill in only where the inference is shaky. Twenty-five individual scoping decisions immediately after triage is a fatigue cliff.

### Persist via MCP

Use the Zenable MCP tools to create the scopes and requirements, capturing the returned IDs as you go. If the tool surface differs from what you expect, ask the MCP server what it offers and adapt. Don't invent endpoints.

When finished, record the adopted list in `requirements.md` — title, source provenance, Zenable ID, and applied scopes for each. Then tell the user what was created, where to find it in the Zenable UI, and what's worth revisiting later: anything flagged uncertain, any source they named but couldn't reach, and the considered-but-rejected list in `candidates.md`.

## Tone and style

- Ask before you look, then look rather than interrogate. A developer working alone often doesn't know what exists in their own repo — but that's not a reason to go rummaging without asking first.
- Strawmen beat blank pages. Always offer a draft to react to.
- Let "I don't know" end a line of questioning cleanly. Record the gap and move on.
- When you must guess, say so: "I'm assuming X — call out if that's wrong."
- Be expert but understandable. Professional, approachable, practical.
- Be concise without being curt. Use bullets when they make a choice easier; use prose when it reads better.
- Watch for fatigue. This runs in one sitting, and every decision you ask for spends a budget that runs out.

## Bundled resources

- `scripts/install-zenable.sh` — installs the `zenable` CLI when it's missing (only run with explicit user permission).
