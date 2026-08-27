# Evidence model — how the report sources its data

Tool reference for the `/z:assessment` report.

## The four layers

A report fact belongs to exactly one layer. Knowing which keeps authored prose,
computed values, and tool output from drifting into each other.

- **Derived** — computed by the renderer (`app.js`) from finding metadata + IDs:
  risk matrix, severity chips, attack-path finding-chains, rec→finding links,
  CVE links. Self-maintaining; fix the finding and these follow.
- **Analysis** — human-authored in `data.js`: finding titles/detail, takeaways,
  overall-risk narrative, trust-boundary prose, scope, strengths, recommendations,
  investigator statement. Stays authored.
- **Context** — raw source material supplied by the engagement: transcripts,
  emails, design docs, diagrams, screenshots. Preserve under `context/` exactly
  as received; cite it, do not rewrite it in place.
- **Evidence** — facts that come from a tool: artifact hashes, dependency/license
  inventory, secrets-scan counts, experiment statistics. These MUST be generated
  from source tool output, never hand-typed — they drift the moment the tree
  changes. This is the layer the transform scripts own.

## Evidence registries (`scripts/*.py` → `evidence/*.json` → inlined)

Everything under `evidence/` is generated-only: direct scanner/tool outputs live
under scoped subdirectories such as `evidence/sbom/`, `evidence/secrets/`, or
`evidence/findings/`; transform outputs live as top-level `evidence/*.json`.
Authored generator specs/configs live outside evidence at the workspace root
when needed, for example `artifacts-spec.json` or `metrics-aliases.json`.

Each transform reads generated source tool output and emits a
schema-conformant JSON with provenance. A build step inlines the rendered subset
into `report/index.html` between `<!-- TAG-BEGIN/END -->` markers (the
`#metrics-data` pattern, generalized), so report facts are generated from
source evidence instead of hand-transcribed into `data.js`.

| Script | Generated source | Output | Renders into |
|---|---|---|---|
| `extract_metrics.py` | git history | `metrics.json` (`#metrics-data`) | repository-history appendix |
| `hash_artifacts.py` | git `cat-file` / fs, from a spec | `artifacts.json` (`#artifacts-data`) | provided-artifacts appendix |
| `sbom_to_dependencies.py` | syft + grype JSON | `dependencies.json` (`#dependencies-data`) | dependency-inventory appendix |
| `trufflehog_to_secrets.py` | trufflehog NDJSON | `secrets.json` (`#secrets-data`) | a strength |
| `collect_experiments.py` | per-experiment `*.experiment.json` | `experiments.json` (`#experiments-data`) | attack-path / finding prose |

Determinism: same generated source input → byte-identical transform output.
Pass `--generated-at ""` to suppress the wall-clock stamp when you need
byte-stable reruns.

Provenance records only what the output proves: tool and version from the
descriptor, source target, output filename, computed result. The invoking CLI
command is not stored in syft/grype output, so it is omitted rather than
re-typed from memory.
