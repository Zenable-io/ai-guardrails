---
name: assessment
description: Run a guided, end-to-end code assessment — frame the engagement, onboard the codebase's requirements via the setup skill, run `zenable check` plus an AI review pass against those same requirements, merge and verify the findings, and produce a polished HTML report bundle. Use this skill whenever the user asks to "scan", "audit", "review", or "assess" a codebase against custom requirements, compliance frameworks, or security concerns; whenever they want a deliverable report (PDF/HTML) summarizing a code review engagement; or whenever they invoke `/z:assessment`. Also trigger for phrases like "do a security review of this repo", "build me a compliance scan report", "I need to audit this codebase against X", or "scan this code for Y".
---

# Zenable assessment

An assessment is the `setup` skill plus validation and reporting. Setup produces
durable, well-scoped requirements; this skill checks the code against them,
verifies every claim it makes, and hands the user a deliverable report.

The skill is collaborative throughout — the user shapes what gets assessed, what
requirements are enforced, and what the final report says. You are the analyst:
gather objective context, ask thoughtful questions, draft strawman content for
the user to react to, and only commit once they've signed off.

## Mental model

Five phases that build on each other. Don't shortcut them — the value comes from
the user's input being woven through, not from running a tool.

1. **Frame & define** — establish the engagement, then run `setup` to co-author
   and persist the requirements
2. **Evaluate** — run `zenable check` AND an AI review pass against those same
   requirements, then merge
3. **Report** — populate the HTML template, walk the user through it, iterate
4. **Verify** — audit every factual claim in the report adversarially
5. **Groom** — gut-check the report's shape with the person who has to stand
   behind it

The interview work in phases 1, 3, and 5 is what makes the report bespoke.
Anything you assume without asking will read as generic.

## Phase 1 — Frame & define

### Frame the engagement first

Do this before handing off to `setup` — the answers change what's worth
collecting and how deep to go.

Ask one or two questions about the user's background so the conversation lands
at the right level:

- Are they a developer or owner of the system assessing a specific concern?
- Are they less familiar, tasked with covering a broader company or audit need?
- Do they want technical detail, executive framing, or both?

Ask how the output will be used — internal only, external audit, customer or
prospect review, third-party/vendor review, public, or another distribution
constraint. Then ask *why* the assessment exists, since it drives requirement
selection and report tone:

- What's prompting this? (audit prep, customer due diligence, pre-acquisition,
  incident response, internal hygiene, certification milestone…)
- Who reads the final report? (board, execs, engineering, external auditor,
  regulator)
- Is this a one-shot deliverable, a baseline to re-run quarterly, or a snapshot
  for negotiation leverage?
- Is there a classification or distribution constraint? (Confidential,
  Recipient-Only, NDA-bounded)

These shape `meta.engagement`, `meta.classification`, the
`investigator.statement`, and how aggressive versus conservative you should be
about flagging findings.

Agree on depth before doing analysis:

- **Fast** — focused answer, fewer requirements, lighter report, no optional
  appendices unless they serve the stated goal.
- **Balanced** — the default workflow.
- **Exhaustive** — auditor-grade detail, richer evidence capture, actor/action
  matrices, trust-boundary diagrams, and the Phase 4 claim audit.

Also settle the assessment's boundary, which `setup` alone won't ask about:

- **Scope** — organization, department, software, platform (Kubernetes, Lambda,
  data warehouse), customer-facing SaaS, internal tool, or something else.
- **Architecture and data flow** — vendors, users, servers, databases, queues,
  clouds, identity providers, integrations, trust boundaries.
- **Data classification and capability** — what data exists; who or what can
  create, read, update, delete, export, or share it.
- **Actors and actions** — normal and adversarial personas: external without
  access, customer user, admin, service account, malicious insider, compromised
  vendor, compromised CI.
- **Success criteria** — what can go wrong, and how would we know we did well?

After the structured questions, switch into looser brainstorming: invite the
user to wander through intended use, weird edge cases, misuse, attack ideas,
surprising dependencies, and failures they worry about. Keep it relaxed; turn
the useful parts into the plan and the requirements.

Record all of this in `frame.md`, and the running narrative of decisions — and
why they changed — in `interview-log.md`.

### Set up the workspace

Establish a workspace inside the target repo (or cwd if there is no repo).
Default location: `./zenable-assessment/<UTC-timestamp>/`. Confirm the location
with the user before creating it.

```
zenable-assessment/<ts>/
  AGENTS.md               # copied from this skill; persistent deterministic-work rules
  CLAUDE.md               # contains @AGENTS.md so Claude loads those rules
  frame.md                # engagement context: audience, use, classification, depth
  interview-log.md        # running narrative of decisions and why they changed
  artifacts-spec.json     # optional generator spec for artifact hashing
  metrics-aliases.json    # optional generator config for git author grouping
  context/                # RAW/UNCHANGED transcripts, emails, docs, diagrams
  evidence/               # GENERATED/CAPTURED ONLY; never hand-edit, rerun tools/scripts
    findings/             # zenable check JSON/SARIF + AI-pass JSON
    sbom/                 # syft/grype JSON, if the dependency appendix is in scope
    secrets/              # trufflehog NDJSON, if a secrets scan is in scope
    research/             # captured external sources with raw files + metadata
    metrics.json          # extract_metrics.py
    artifacts.json        # hash_artifacts.py
    dependencies.json     # sbom_to_dependencies.py
    secrets.json          # trufflehog_to_secrets.py
    experiments.json      # collect_experiments.py
  experiments/            # reproduction scripts/fixtures/captures; emits *.experiment.json
  report/                 # working report template copy (edit data.js here)
  dist/                   # GENERATED build output; includes assessment-bundle.zip
```

Copy the bundled workspace instructions and report template into it:

```bash
cp <skill-path>/assets/workspace/AGENTS.md <workspace>/AGENTS.md
cp <skill-path>/assets/workspace/CLAUDE.md <workspace>/CLAUDE.md
cp -R <skill-path>/assets/template/. <workspace>/report/
```

The `AGENTS.md`/`CLAUDE.md` pair keeps the deterministic evidence posture
available after this skill run ends, when another agent or reviewer continues
from the workspace.

### Run `setup`

Hand off to the bundled `setup` skill for everything from pre-flight through
persisted requirements: CLI install, authentication, MCP availability,
repository identity, standards discovery, candidate mining and triage,
requirement co-authoring, scoping, and creation through the Zenable MCP.
Invoke it as `z:setup` (the user can also type `/z:setup`).

Do not restate or re-implement any of that here — a second copy of the
pre-flight and requirement-authoring workflow will drift from setup's.

Two things to pass it:

- **The workspace you just created.** Setup defaults to its own
  `./zenable-setup/<ts>/`; tell it to write its notes (`sources.md`,
  `candidates.md`, `codebase-context.md`, `requirements.md`) into the assessment
  workspace instead, so the whole engagement lives in one directory.
- **The framing from `frame.md`.** Depth, audience, classification, and the
  scope boundary all change what setup should collect and how hard to push on
  requirement count. Setup mines the standards a team has already written down;
  the engagement framing tells it which of those matter here.

Setup owns the pre-flight gates. If it stops because the CLI isn't installed,
the user isn't authenticated, or the MCP isn't available, this skill stops too —
without persistent scopes and requirements, most of the workflow's value is gone.

When setup finishes, `requirements.md` holds the adopted requirements with their
Zenable IDs and scopes. Those IDs are what findings reference later via
`requirementIds`, so the assessment can cross-link every finding back to the
requirement it violates.

### Evidence discipline

Everything under `context/` is source material from the engagement: transcripts,
emails, meeting notes, design docs, diagrams, screenshots. Add it exactly as
received. Do not edit, redact, summarize, normalize, or convert a context file
in place. If a cleaner summary or derived fact is useful, put that in
`frame.md`, `data.js`, or generated `evidence/` and link back to the untouched
context file.

Everything under `evidence/` is produced by a command, tool, script, or captured
source fetch. Never edit it by hand: edit `data.js` for prose, edit root-level
generator specs such as `artifacts-spec.json` or `metrics-aliases.json`, or edit
experiment scripts under `experiments/`, then rerun the producing tool. Every
number in the generated appendices traces to a tool or script output, not a
typed value. For byte-stable output, pass `--generated-at ""` to scripts that
support it; re-running one over the same inputs then reproduces byte-identical
output.

All analysis must be deterministic. If you need a new fact, create or rerun a
tool, script, or capture that produces evidence for it. If a fact cannot be made
deterministic from available context, mark it low confidence and ask the user
whether to gather more evidence or leave it out.

### Metrics snapshot

Once the scope is settled, run the metrics script for the objective baseline.
This one needs no user input:

```bash
uv run --script <skill-path>/scripts/extract_metrics.py \
  --repo-root <target-repo> \
  --out <workspace>/evidence/metrics.json \
  --html <workspace>/report/index.html \
  --generated-at ""
```

**Assessing a sub-package of a monorepo?** Pass `--path-prefix <subdir>`
(repo-relative) so the metrics describe the sub-package's history, not the whole
repo's. Without it the script walks every commit reachable from HEAD, which
dilutes the metrics with unrelated activity and misleads readers who think
they're looking at the scoped package. Set `meta.target` in `data.js` to match.

If the target repo has a long history with author identity drift (people
changing names or emails), offer to take a list of manual alias groups from the
user, save it as `<workspace>/metrics-aliases.json`, and pass
`--aliases <workspace>/metrics-aliases.json`. Don't require it.

## Phase 2 — Evaluate

### `zenable check` pass

Run the CLI against the target. Exact flags depend on the scope settled in
Phase 1; ask the user before running anything noisy or destructive. Typical:

```bash
zenable check --branch \
  --format text,json=<workspace>/evidence/findings/zenable-check.json,sarif=<workspace>/evidence/findings/zenable-check.sarif
```

If the user wants the full tree rather than the branch diff, drop `--branch` and
pass globs. Show them the command before running it.

**Filter known-noise rules before populating findings.** Some rules are test
fixtures or universal-good-practice nags that fire on every file and dilute the
signal. When you see floods of identical findings of that shape — same rule,
scattered across unrelated files, no real risk — drop them from the merged set
and note in `interview-log.md` which rules you suppressed and why. If you're
unsure whether a rule is signal or noise, ask the user before suppressing.

### AI review pass

Now do a second pass the CLI cannot do. For each requirement, walk the relevant
files looking for what the deterministic scanner missed: architectural concerns,
threat-model gaps, design-level issues, anything needing judgment.

Keep AI-pass findings in the same schema as the `zenable check` JSON output so
the merge is mechanical. Write them to `evidence/findings/ai-review.json` as
generated output, not hand-authored report prose. Tag every finding with
`source: "ai-review"` and a `requirementIds` array so it traces back to the
requirement setup persisted.

If a requirement is best evaluated by reading specific files, read them
directly — don't sample. The user will judge the report by how grounded each
finding is.

### Merge

Combine the two streams into a single deduplicated list:

- Same file + same rule or requirement + overlapping line range → one merged
  finding, `source: "merged"`, both sources captured in evidence
- Severity is the max of the two
- Recommendations: one per *finding cluster*, not one per source

The merged set populates `findings[]` in `data.js`. Set `requirementIds` on each
so the renderer cross-links to the Custom Requirements section. Score every
finding using the rubric documented in `assets/template/data.js`.

### Collect optional tool evidence

Only run tools that match the engagement scope. Put direct tool output under a
scoped directory in `evidence/`; transform scripts then turn it into
deterministic top-level `evidence/*.json` registries.

Do not install these tools without explicit user permission. If they're missing,
show the install link, ask, and proceed only after approval.

- Syft: `https://github.com/anchore/syft#installation`
- Grype: `https://github.com/anchore/grype#installation`
- TruffleHog: `https://github.com/trufflesecurity/trufflehog#installation`

On macOS, commonly: `brew install syft grype trufflehog`

Source-tree SBOM and vulnerability capture:

```bash
mkdir -p <workspace>/evidence/sbom
syft <target-repo> -o json > <workspace>/evidence/sbom/source-tree.syft.json
grype sbom:<workspace>/evidence/sbom/source-tree.syft.json -o json \
  > <workspace>/evidence/sbom/source-tree.grype.json
```

TruffleHog output is NDJSON. Never paste secret values into `data.js`; the
transform emits redacted summaries only.

```bash
mkdir -p <workspace>/evidence/secrets
trufflehog filesystem <target-repo> --json \
  > <workspace>/evidence/secrets/trufflehog.fs.json
trufflehog git file://<target-repo> --json \
  > <workspace>/evidence/secrets/trufflehog.git.json
```

### Generate evidence registries

Anything that surfaces a hash, a dependency or license count, or a secrets-scan
number belongs in a generated `evidence/*.json`, never typed into `data.js` by
hand — those numbers drift the moment the tree changes. Run only the transforms
whose appendix is in scope:

```bash
# Artifact hashes (author a small spec listing what to hash)
uv run --script <skill-path>/scripts/hash_artifacts.py \
  --repo-root <target> --spec <workspace>/artifacts-spec.json \
  --commit <pinned-sha> --out <workspace>/evidence/artifacts.json \
  --generated-at ""

# Components/licenses/vulns from the syft+grype output in evidence/sbom/
uv run --script <skill-path>/scripts/sbom_to_dependencies.py \
  --sbom-dir <workspace>/evidence/sbom --out <workspace>/evidence/dependencies.json \
  --generated-at ""

# Secrets-scan summary from trufflehog NDJSON (redaction-safe; never emits Raw)
uv run --script <skill-path>/scripts/trufflehog_to_secrets.py \
  --secrets-dir <workspace>/evidence/secrets --out <workspace>/evidence/secrets.json \
  --generated-at ""

# Demonstrated-attack stats — each experiment emits its OWN *.experiment.json
uv run --script <skill-path>/scripts/collect_experiments.py \
  --experiments-dir <workspace>/experiments --out <workspace>/evidence/experiments.json \
  --generated-at ""
```

Each script also takes `--html <report>/index.html` to inline its result at build
time (Phase 3). Authored prose — findings, strengths, narratives — stays in
`data.js`; the evidence numbers come from these files.

The three trees serve different purposes:

- `context/` — raw source material, preserved unchanged and cited, never
  rewritten in place.
- `evidence/` — generated JSON registries and direct tool output supporting
  appendix rows, counts, hashes, and scan summaries. Nothing here is hand-edited.
- `experiments/` — reproduction scripts, input fixtures, and captured output for
  demonstrated attacks or behavioral proofs. Each experiment emits its own
  `*.experiment.json`; `collect_experiments.py` aggregates them.

The published report can link to files in any of these trees without embedding
them. In `data.js` prose use the inline syntax
`[label](download:context/path/to/file.md)`, or `download:evidence/...` /
`download:experiment/...` for generated artifacts and reproduction files. The
renderer emits `data-download-kind` + `data-download-path` links. In the Zenable
app the report runs in a sandboxed iframe and cannot fetch authenticated files
itself, so the iframe posts `{type: "report:download", kind, path, nonce}` to the
parent, which verifies the nonce and fetches the file with the user's normal
session. Standalone offline opens simply ignore that bridge.

External research becomes evidence only when captured reproducibly. Put each
source under `evidence/research/<topic-or-source>/` with:

- the unmodified raw download (`raw.html`, `raw.pdf`, `raw.json`, …)
- optional derived markdown or text for easier reading
- a metadata JSON with source URL, retrieval command or service, timestamp,
  content type, and any conversion tool used

Do not cite live web pages as if they are stable. Cite the captured evidence
file and keep the original URL in its metadata.

## Phase 3 — Report

### Template walkthrough

Before populating anything, walk the user through the section list and ask which
they want. The template ships with all of these — keeping a section means
filling it; removing one means deleting both the `data.js` field and the HTML
`<section>`.

- **1. Executive summary** — required
- **2. Scope** — required (Phase 1 framing goes here)
- **3. Trust Boundary, Data Flow & Attack Paths** — optional; a mermaid data-flow
  diagram plus demonstrated attack paths. Strong for engagements with a clear
  trust boundary. Hides when `trustBoundary`/`attackPaths` stay null.
- **4. SAMM maturity** — optional; useful for exec or auditor audiences
- **5. Strengths** — optional but recommended (a report of nothing but findings
  reads as adversarial)
- **6. Risk matrix** — required if there are findings
- **7. Findings** — required if there are findings
- **8. Confirmed exploitable CVEs** — optional; only if the scope included
  dependency exploitability analysis
- **9. Custom Requirements Review** — required; each requirement setup persisted
  gets a status here
- **10. Recommendations** — required if there are findings
- **11. Investigator statement** — required; must include the standing
  attestation, near-verbatim, that "All AI usage was via inference providers
  which do not retain or train on inputs or outputs."
- **A. Provided artifacts** — optional; SHA-256 of the inputs, from
  `hash_artifacts.py`
- **B. Possible (unconfirmed) findings** — optional; things worth more research
- **C. Repository history** — required; the Phase 1 metrics populate it
- **D. License & dependency inventory** — optional; from
  `sbom_to_dependencies.py`

Custom appendices are allowed, but only when the user asks for that line of
analysis or the engagement clearly requires it. Do not push dead-code,
reachability, performance, or privacy appendices as part of the baseline. If you
add one, generate an `evidence/<topic>.json` registry from deterministic
context/evidence/experiment inputs and inline it into the `extensions-data`
block in `report/index.html`; do not hand-author appendix rows in HTML.

For every "no", remove the matching `<section>` block from the user's
`report/index.html` and the matching field from `data.js`. Don't leave dead
containers.

**After pruning, renumber the numbered sections (1–11).** The template ships
with numbered headings and a matching TOC. Dropping sections 3 and 7 leaves the
TOC reading 1, 2, 4, 5, 6, 8, 9, 10 — which looks broken. Renumber sequentially
in both the `<nav class="toc">` block and the section `<h2>` headings.

**Appendices reletter and prune themselves — leave them alone.** `app.js`
re-letters every `section[id^="appendix-"]` A, B, C, … by document order at
render time, so removing one never leaves a gap. Keep appendix ids as stable
slugs (`appendix-artifacts`, `appendix-deps`, …), never letter-based. The empty
"Possible (Unconfirmed) Findings" appendix is removed automatically when
`unconfirmed` is empty; other data-driven sections that render empty are pruned
the same way, and any TOC card whose target section is gone is dropped.

**Reference appendices by slug, never by letter.** In prose anywhere, write a
reference as a `{{appendix:<slug>}}` token — it resolves at render to a live
"Appendix X" link with the correct positional letter. Hardcoding "Appendix D"
breaks the moment an earlier appendix is pruned. A token whose appendix was
pruned drops itself.

### Populate `data.js`

`data.js`'s `window.REPORT` object is the canonical report payload. Keep keys
camelCase. The upload service treats the report as an opaque static bundle; a
new section must be rendered by this template before upload.

Edit `<workspace>/report/data.js` — the copy made during workspace setup, not
the bundled asset.

**Identity model — use stable keys, never hand-number.** Every finding,
strength, recommendation, and attack path carries a short opaque `key` (e.g.
`"k3f9wq"`); the human-friendly ids (`F-NNN` / `S-NNN` / `REC-NN` / `AP-N`) are
derived at render time — findings by severity then impact×likelihood, the rest by
source order — so reordering or rescoring renumbers everything automatically.
Reference another item from prose as `[[key]]` and the renderer resolves it to
the live id and link. Link findings from recommendations via
`relatedFindingKeys`, from attack paths via `chain`, and a finding's
recommendation via `recommendationKey`. Never write a literal `F-007` in prose.
Generate a fresh key per new item (any short random base36 string).

Fill in:

- `meta`, `investigator`, `scope` — from `frame.md`
- `samm.domains[*].score` — if section 4 is in; assess each domain against what
  you've seen
- `strengths` — what's *good* about the codebase, with the same evidence rigor as
  findings
- `findings` — the merged set, scored against the rubric
- `cves` — only confirmed-exploitable; dependency CVEs without a usable code path
  belong in a single roll-up finding
- `customRequirements.sections` — one per requirement, with `requirementId` set
  to the Zenable ID from `requirements.md`
- `recommendations` — one per finding cluster, citing `relatedFindingKeys`
- `trustBoundary`, `attackPaths` — only if section 3 is in; author the
  `summary`/`points`/`mermaid` source and the demonstrated attack paths.
  **Validate the mermaid source before building** — one syntax error renders a
  "Syntax error in text" bomb instead of the diagram. Lint it with the mermaid
  CLI (`npx -y @mermaid-js/mermaid-cli -i diagram.mmd -o /tmp/out.svg`, which
  pins the same renderer the report uses) or paste it into https://mermaid.live.
  Gotcha: in sequence diagrams a `;` ends a statement, so any semicolon inside a
  `Note` or message label breaks the parse — use `—` or `,` instead.
- `unconfirmed` — only if Appendix B is in
- Appendix intros — pass `note` in the artifact spec consumed by
  `hash_artifacts.py`, and `--note` to `sbom_to_dependencies.py`. Those are the
  ONLY authored fields in those appendices; every row comes from the generated
  inline blocks. Do not hand-type hashes, component lists, or row data into
  `data.js`
- `takeaways` — last; 3–5 sentences an executive could read in 60 seconds

### Inline the evidence and metrics

Inline the git metrics and every generated `evidence/*.json` by passing
`--html <workspace>/report/index.html` to each transform script. Each writes its
JSON between its own `<!-- *-BEGIN/END -->` markers, and the renderer reads those
generated blocks. Re-run a transform any time its source tool output or an
experiment output changes.

The report HTML is otherwise self-contained: `styles.css`, `data.js`, and
`app.js` are inlined by the bundle builder. The chart libraries are not copied
into each report — they are version-pinned static files hosted by the Zenable
app (`/report-assets/echarts-*.min.js`, `/report-assets/mermaid-*.min.js`),
loaded DYNAMICALLY by `app.js` (`CHART_LIBS`, with SRI pins) and never via static
`<script src>` tags, which block the HTML parser and let a stalled network
middlebox wedge the whole report. Do not add `vendor/` copies of these libraries
to the skill or to report workspaces.

### Build the bundle

Once `report/data.js`, `context/**`, `evidence/**`, `experiments/**`, and the
inlined evidence blocks are final:

```bash
uv run --script <skill-path>/scripts/build_report.py \
  --report-dir <workspace>/report \
  --context-dir <workspace>/context \
  --evidence-dir <workspace>/evidence \
  --experiments-dir <workspace>/experiments \
  --out-dir <workspace>/dist
```

The builder writes `report.html`, `meta.json`, `context/**`, `evidence/**`, and
`experiments/**` under `<workspace>/dist/`, then
`<workspace>/dist/assessment-bundle.zip`. `meta.json` includes a `report_slug`
hint derived from the report metadata; the upload service treats that as input
only and does the final path-safe sanitization server-side. `report.html`
contains NO static external resource tags — the chart libraries load dynamically
from `app.js`, and the builder fails on any static tag that remains.

### Open the report

Open `report/index.html` in the user's browser for local review and walk them
through it section by section. At each section, ask:

- Does this match how you'd characterize it?
- Anything missing?
- Anything overstated or understated?
- Is the severity right?

This is the most important step. Iterate on `data.js` from their feedback,
re-open the page, and confirm. Repeat until they say it's right.

When done, tell the user where `assessment-bundle.zip` lives. Offer to print or
export to PDF if their goal is a static deliverable.

### Upload

The upload path is the web app. Open `https://www.zenable.app/assessments` and
use the top-right upload button to upload `<workspace>/dist/assessment-bundle.zip`.
The bundle must be 100 MiB or smaller.

If this is the tenant's first assessment, Assessments may not appear in the left
sidebar yet; browsing directly to `https://www.zenable.app/assessments` is
expected to work. After the first upload and a logout/login cycle, the sidebar
item appears by design.

## Phase 4 — Verify (claim audit)

A finished report is a pile of factual assertions a reader will rely on: hashes,
file:line citations, statistics, severity counts, reproduced attacks, license
facts. Before the report is final — or whenever the user wants a rigor pass —
audit every claim adversarially. This phase is mechanical and fan-out heavy. It
is opt-in: run it when the engagement is high-stakes (external auditor,
regulator, acquisition) or when the user asks to "verify", "fact-check", or
"validate the report".

### Step 1 — Build the claim inventory

Enumerate every factual claim in the report into a single `claims-inventory.md`.
The source of truth is the populated `report/data.js` plus the metrics inlined
into `report/index.html`. A "claim" is anything the reader is meant to rely on:
findings, scores, dates, names, behavior, code references, statistics, license
and dependency facts, hashes, git metrics. UI captions and rendering logic are
not claims.

Give every claim a stable ID (e.g. `C-F007-7`) and record the assertion, where it
renders (section plus `data.js` location), and the evidence the report currently
cites. Cross-reference repeated assertions so the same fact stated in five places
is verified once and checked for consistency across all five. The inventory is
the audit's work-list — a claim not inventoried is a claim not checked.

### Step 2 — Group and fan out verification

Split the inventory into tractable groups of roughly 10–25 related claims, by
report section. Then run two phases:

1. **Verify** — one independent skeptic per group. Each must *open the cited
   files, run git and grep, recompute hashes, and re-run reproduction
   experiments* rather than trusting the report's own evidence strings. Rules:
   - Default to **unsure**. Mark **valid** only when primary evidence was
     inspected or reproduced and holds. Mark **invalid** when primary evidence
     contradicts the claim as written — wrong hash, line, or count; non-existent
     file; broken logic; or *overstatement*, meaning technically true but
     oversold. External facts that can't be checked offline (CVE IDs, EOL dates,
     academic citations) are **unsure**, stated as such, never guessed.
   - Return structured output per claim:
     `{id, verdict (valid|invalid|unsure), confidence, summary, checked, result, counter}`.
2. **Adjudicate** — pipe each group's result into a second, independent reviewer
   that re-checks *only* the claims marked invalid or unsure, from scratch. This
   adversarial cross-check either confirms the doubt or rehabilitates the claim,
   and catches first-pass mistakes in both directions. Let each group adjudicate
   as soon as its verify stage finishes rather than waiting on all groups.

The adjudicated verdict overrides the first pass on contested claims.

### Step 3 — Bucket into three linked outputs

Aggregate deterministically — a small script, not by hand, since there can be
hundreds of claims — into three files next to the inventory, each entry linking
back to its claim ID:

- `claims-review-valid.md`
- `claims-review-invalid.md`
- `claims-review-unsure.md`

Surface the **hotspots**: claims the two passes disagreed on (verdict flips),
"valid" claims that still carry a caveat or overstatement, and where invalids
cluster (often an appendix or a headline). Lead each file with a short summary so
the user sees the shape before the per-claim detail.

### Step 4 — Fix, then discuss

- **Fix every provably-invalid claim** in `data.js`, re-inlining metrics if those
  changed: stale hashes, wrong line citations, off-by-one counts, false
  interpretations, overstated wording. Re-verify each fix.
- **Then discuss the unsure claims and caveats with the user.** These are
  judgment calls — non-reproducible-by-construction values, deployment-dependent
  assertions, wording that's defensible but soft. Don't silently rewrite them;
  walk the user through each and let them decide.

A core finding rarely collapses in this pass. The usual yield is wording
overstatements, stale fingerprints, and appendix bookkeeping — exactly the class
of error that erodes credibility with a skeptical reader.

## Phase 5 — Groom (gut-check)

Phases 1–4 make the report *correct*; this one makes it *feel right* to the
person who has to stand behind it. Before delivery, pressure-test the report's
**shape** with the user — distribution, severity calibration, emphasis — as a
fast gut-check interview. The audience defined in `frame.md` drives which
dimensions matter, so re-read it first. Run this before any report is final.

### Step 1 — Summarize the shape, not the substance

Compute a one-screen profile from the finished `data.js` and present it back —
trends and groupings only:

- Finding count, broken down by severity and by theme.
- The 3 highest-risk findings and the 3 lowest, each as a single line.
- Overall risk posture, strengths count, and the headline takeaways.
- Any lopsidedness worth naming: a category with a single finding, an empty
  severity bucket, a theme that dominates.

The user should be able to react to the whole engagement in thirty seconds. If
you're quoting file:line or restating a finding's mechanics, you've gone too deep.

### Step 2 — Ask about ten questions, grouped by dimension

Generate them at runtime, tailored to the audience and goals in `frame.md`, not
from a fixed list. Group them so the user reasons one axis at a time, and cover
at least:

- **Distribution** — does the count per category feel right? Anything expected
  that isn't here, or a bucket heavier or lighter than your gut says?
- **Severity calibration** — are the Highs actually the biggest risks, and the
  Lows actually minor? Anything ranked too hot or too cold?
- **Emphasis** — does the overall posture, and the lead finding, match how you'd
  open this conversation with the reader?
- **Groupings** — do any findings read as duplicates that should merge, or as one
  finding hiding two? Do the themes group the way the reader thinks?
- **Audience fit** — will the reader find this at the right altitude and
  actionable? Where will they push back?
- **Balance** — do the strengths feel proportionate, or does the whole read too
  harsh or too soft?

Ask them as quick gut-feel reactions, not homework. Offer your own read first so
the user is reacting, not authoring.

### Step 3 — Reshape, then rebuild

Turn the reactions into structural edits — re-rank severities, merge or split
findings, re-weight emphasis, add or trim strengths, move a buried finding up —
then rebuild and re-upload. These are shape changes, so re-run the relevant
slice of Phase 4 on anything you re-worded. Loop until the user's gut says it's
right; that sign-off is the real exit criterion for the engagement.

## Send feedback

At the end of the engagement — after the Phase 5 sign-off, or after the upload
if the user stops there — send feedback on how the run went. Two separate
surfaces:

- `zenable self feedback --message "..." --type=bug|feature_request|other` —
  anything about Zenable itself: an MCP tool that errored, a CLI flag whose
  behavior surprised you, a filter or parameter or capability the assessment
  needed and didn't have. Authenticated; 2000 chars max.
- `zenable report friction --message "..."` — friction in this coding session
  that is NOT about Zenable: pain points, inefficiencies, gripes, competing
  priorities, disagreements with the instructions or tooling you were handed.
  1024 chars max. Safe to run anytime, and a silent no-op when the user isn't
  signed in.

Verdicts on Zenable hook findings are a third surface — those go to
`zenable finding feedback`, never here.

Write about what actually happened in THIS engagement: name the phase, the
tool, or the thing that got in the way. `setup` sends its own feedback in
Phase 1, so don't re-send what it already covered, and don't repeat yourself
within a session. Send nothing when there is genuinely nothing to say.
Delegate the calls to a subagent so they run in parallel and stay out of your
context.

## Tone and style

- Default to asking, not assuming. When you can guess the answer, ask anyway —
  sometimes the user has a reason you'd miss.
- When you must guess, say so: "I'm assuming X — call out if that's wrong."
- Let "I don't know" end a line of questioning cleanly. Record the gap and move on.
- Strawmen beat blank pages. Always offer a draft to react to.
- Never invent findings to fill space. If a section has nothing real, it says
  nothing.
- Be expert but understandable. Professional, approachable, practical.
- Keep the conversation relaxed enough that the user can brainstorm. The final
  report stays crisp and evidence-driven.
- Be concise without being curt. Bullets when they make a comparison or choice
  easier; prose when it reads better.
- Avoid dumping filenames, line numbers, and implementation detail unless the
  user asks or the evidence needs it.
- Every assertion needs evidence. If evidence is missing, mark confidence low or
  go create deterministic evidence.
- Prefer experiments, scripts, and tool output over impressions. Ad hoc scripts
  belong in `experiments/`.
- Watch for fatigue. This runs across a long session, and every decision you ask
  for spends a budget that runs out.

## Bundled resources

- `scripts/extract_metrics.py` — git-derived metrics into `metrics.json`,
  optionally inlined into the report HTML. Run once per assessment.
- `scripts/hash_artifacts.py` — SHA-256 and deterministic tree-hash of the
  provided artifacts, from a spec, into `evidence/artifacts.json`. Pin with
  `--commit` for reproducible hashes.
- `scripts/sbom_to_dependencies.py` — syft/grype output into
  `evidence/dependencies.json` with computed component, license, and
  vulnerability counts.
- `scripts/trufflehog_to_secrets.py` — trufflehog NDJSON into
  `evidence/secrets.json` (counts by detector and verified status).
  Redaction-safe: emits `Redacted`, never `Raw`.
- `scripts/collect_experiments.py` — aggregates per-experiment
  `*.experiment.json` into `evidence/experiments.json`.
- `scripts/build_report.py` — packages `<workspace>/report` into
  `assessment-bundle.zip`; inlines `styles.css`, `data.js`, and `app.js` into
  `report.html`, derives `meta.json`, copies context, evidence, and experiments,
  and preserves the root-relative `/report-assets/` chart-library references.
- Every transform takes `--out <evidence/x.json>` and an optional
  `--html <report/index.html>` to inline at build time between its
  `<!-- *-BEGIN/END -->` markers. Tests live in `scripts/tests/`
  (`uv run --with pytest pytest scripts/tests/`).
- `assets/template/` — the report template (`index.html`, `app.js`, `styles.css`,
  `data.js`). Copy it to `<workspace>/report/` at workspace setup and edit the
  copy. It references `/report-assets/echarts-5.6.1.min.js` and
  `/report-assets/mermaid-11.15.0.min.js`; do not vendor those files.
- `assets/workspace/` — `AGENTS.md` + `CLAUDE.md` copied into the workspace so
  the deterministic evidence posture survives the skill run.
- `references/EVIDENCE-MODEL.md` — the evidence model (Derived / Analysis /
  Context / Evidence layers) and the transform-script → `evidence/*.json` →
  inline contract. Read before touching evidence generation or the appendix
  renderers.
