# Assessment Workspace

This workspace is evidence-driven and deterministic.

- Keep source context unchanged under `context/`.
- Put generated tool output, captures, and registries under `evidence/`.
- Put reproduction scripts, fixtures, and experiment outputs under `experiments/`.
- Do not hand-edit files under `evidence/`; change the source config or script, then rerun it.
- Put ad hoc analysis scripts in `experiments/`.
- Do not install tools on the user's machine without explicit permission.
- Treat unsupported assertions as low confidence until backed by context, evidence, or experiments.
- External research used as evidence needs raw capture plus metadata: source URL, retrieval command or service, timestamp, content type, and conversion tool when applicable.
- Link report claims to supporting `context/**`, `evidence/**`, or `experiments/**`.
- Build artifacts belong under `dist/`.
