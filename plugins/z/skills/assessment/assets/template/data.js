/*
 * Report data — single source of truth for the template.
 *
 * The skill fills this in during the report-population step. Every field
 * is documented in-place so a future run (or a human revisor) can see what
 * each section expects.
 *
 * Conventions:
 *   - Empty arrays / null fields are intentional placeholders — the renderer
 *     just hides the corresponding section block.
 *   - Severity, likelihood, and impact are derived from the numeric inputs
 *     on each finding (see the rubric below). Do not hand-set `severity`.
 *   - For sections the user opted out of during the report walkthrough,
 *     leave the corresponding container empty and also remove (or hide) the
 *     section in index.html.
 */

window.REPORT = {
  /* ------------------------------------------------------------------ */
  /* Cover / engagement metadata                                        */
  /* ------------------------------------------------------------------ */

  meta: {
    client: "", // The recipient / commissioning organization
    engagement: "Code Scan", // e.g. "Third-Party Code Review", "SOC 2 Pre-Audit"
    target: "", // Repo + identifier — e.g. "acme-billing (github.com/acme/billing)"
    version: "", // Branch / tag / HEAD sha
    date: "", // YYYY-MM-DD
    location: "", // Where the analysis was conducted
    classification: "", // e.g. "Confidential — Recipient Use Only"
    reportId: "__REPORT_ID__", // Server-stamped uuidv7 at upload time
  },

  investigator: {
    primary: "", // Lead reviewer name
    title: "", // Lead reviewer title
    analysisDates: "", // e.g. "May 20 – June 29, 2026" — the period the analysis was conducted
    contributors: [], // Additional names
    statement:
      "All AI usage was via inference providers which do not retain or train on inputs or outputs.", // Free-form attestation / methodology statement — lead with the engagement-specific methodology, then keep this standing AI-usage attestation verbatim
  },

  /* ------------------------------------------------------------------ */
  /* Executive summary                                                  */
  /* Severity counts are derived from findings[] at render time.        */
  /* `takeaways` are the headline 3–5 bullets for executive readers.    */
  /* ------------------------------------------------------------------ */

  takeaways: [],

  /* ------------------------------------------------------------------ */
  /* Scope                                                              */
  /* ------------------------------------------------------------------ */

  scope: {
    inScope: [], // Enumerate every artifact, branch, module reviewed
    outOfScope: [], // Anything explicitly excluded (CI/CD, runtime, infra, etc.)
    notes: [], // Methodology caveats
  },

  /* ------------------------------------------------------------------ */
  /* Trust boundary, data flow & demonstrated attack paths              */
  /* Whole section hides when both keys are null. `mermaid` is a mermaid */
  /* diagram source string (e.g. a sequenceDiagram); rendered via the    */
  /* version-pinned mermaid asset. `points`/`evidence` accept inline     */
  /* markdown. Each attack path chains finding IDs (`chain`) that        */
  /* deep-link into the Findings section.                               */
  /* ------------------------------------------------------------------ */

  trustBoundary: null, // { summary, mermaid, points: [], evidence: [] }

  attackPaths: null, // { summary, note, paths: [ { key, name, attacker, chain: [findingKey], steps: [], result, evidence: [] } ] }

  /* ------------------------------------------------------------------ */
  /* SAMM-aligned maturity assessment                                   */
  /* Scoring band convention (OWASP SAMM-aligned):                      */
  /*   0.0–0.5  Legacy                                                  */
  /*   0.5–1.0  Traditional                                             */
  /*   1.0–2.0  Modern                                                  */
  /*   2.0–3.0  Cloud-Native                                            */
  /* Set `score` to a number (0–3); null = unassessed (section hidden). */
  /* ------------------------------------------------------------------ */

  samm: {
    bands: [
      { name: "Legacy", min: 0.0, max: 0.5, color: "rgba(123,135,148,.55)" },
      { name: "Traditional", min: 0.5, max: 1.0, color: "rgba(194,143,18,.55)" },
      { name: "Modern", min: 1.0, max: 2.0, color: "rgba(0,127,127,.55)" },
      { name: "Cloud-Native", min: 2.0, max: 3.0, color: "rgba(0,186,174,.65)" },
    ],
    domains: [
      { key: "governance", name: "Governance", score: null, summary: "" },
      { key: "design", name: "Design", score: null, summary: "" },
      { key: "implementation", name: "Implementation", score: null, summary: "" },
      { key: "verification", name: "Verification", score: null, summary: "" },
      { key: "operations", name: "Operations", score: null, summary: "" },
    ],
  },

  /* ------------------------------------------------------------------ */
  /* Identity model: every finding / strength / recommendation / attack */
  /* path carries a stable opaque `key` (short, e.g. "k3f9wq"). The      */
  /* human ids (F-NNN / S-NNN / REC-NN / AP-N) are DERIVED at render     */
  /* time and never stored — findings number by severity then           */
  /* impact×likelihood, strengths/recs/attacks by source order. Refer to */
  /* another item in prose as [[key]]; the renderer resolves it to the   */
  /* live id + link. Reordering or rescoring renumbers everything        */
  /* automatically.                                                      */
  /* ------------------------------------------------------------------ */
  /* Strengths — positive observations                                  */
  /* { key, title, detail }                                             */
  /* ------------------------------------------------------------------ */

  strengths: [],

  /* ------------------------------------------------------------------ */
  /* Findings (risks)                                                   */
  /*                                                                    */
  /* Scoring model:                                                     */
  /*   likelihoodInputs (CVSS-aligned, scored 0–100 each):              */
  /*     exposure:        how reachable the issue is                    */
  /*                      Internal=15 / Local=35 / Adjacent=60 / Net=90 */
  /*     precondition:    setup an attacker needs                       */
  /*                      High=15 / Medium=40 / Low=70 / None=95        */
  /*     discoverability: how visible the issue is                      */
  /*                      Arch=25 / SrcReview=50 / Scanner=75 / Pub=95  */
  /*   likelihoodScore = 0.5*exposure + 0.3*precondition + 0.2*disc.    */
  /*                                                                    */
  /*   impactInputs (0–100 each):                                       */
  /*     scope:          blast radius                                   */
  /*                     SingleRecord=25 / Subset=55 / AllTenants=90    */
  /*     sensitivity:    data category                                  */
  /*                     Internal=25 / PII=60 / PHI=85 / KeyMaterial=95 */
  /*     recoverability: cost to remediate after exploit                */
  /*                     Easy=25 / Hard=60 / Irreversible=95            */
  /*   impactScore = avg(scope, sensitivity, recoverability)            */
  /*                                                                    */
  /* Finding severity values are normalized as Critical / High / Medium */
  /* / Low. Aliases such as lowercase values, Moderate, warn, and error */
  /* are accepted by the renderer/bundler, but prefer canonical values  */
  /* in authored data.js. Risk-matrix axis bucket labels (Low /         */
  /* Moderate / High) are derived separately from numeric likelihood    */
  /* and impact scores at 33.33 / 66.67 thresholds.                     */
  /*                                                                    */
  /* Each finding should cite the requirement(s) it violates in         */
  /* `requirementIds` so the report can cross-link finding → requirement*/
  /* in the Custom Requirements section.                                */
  /*                                                                    */
  /* Finding shape:                                                     */
  /*   { key, title, severity, likelihoodInputs, impactInputs, detail,  */
  /*     evidence: [], relatedCveIds: [], requirementIds: [],           */
  /*     recommendationKey, source }                                    */
  /*   source ∈ { "zenable-check" | "ai-review" | "merged" } — origin   */
  /*   of the finding for traceability.                                 */
  /* ------------------------------------------------------------------ */

  findings: [],

  /* ------------------------------------------------------------------ */
  /* Confirmed Exploitable CVEs                                         */
  /* Only entries with a confirmed exploitable pathway through this     */
  /* code. Dependency CVEs without a usable code path belong in a       */
  /* single roll-up finding rather than enumerated individually.        */
  /*                                                                    */
  /* CVE shape:                                                         */
  /*   { id, package, affectedRange, observedVersion, fixedIn,          */
  /*     cvss: { version, score, severity, vector },                    */
  /*     exploitablePathway, relatedFindingKey, reference }             */
  /* ------------------------------------------------------------------ */

  cves: [],

  /* ------------------------------------------------------------------ */
  /* Custom Requirements Review                                         */
  /*                                                                    */
  /* One section per user-defined requirement from the interview. Each  */
  /* mirrors a Zenable scope/guardrail created via the MCP server.      */
  /* Use `requirementId` so findings can link back here.                */
  /*                                                                    */
  /* status ∈ { ok | ok-with-concern | risk | scope-limited }           */
  /*                                                                    */
  /* { key, requirementId, title, question, status, finding, evidence } */
  /* ------------------------------------------------------------------ */

  customRequirements: {
    summary: "",
    sections: [],
  },

  /* ------------------------------------------------------------------ */
  /* Recommendations — each links back to its source finding(s).        */
  /* priority: Immediate | Near-term | Strategic                        */
  /* { key, priority, title, relatedFindingKeys: [], detail }           */
  /* ------------------------------------------------------------------ */

  recommendations: [],

  /* ------------------------------------------------------------------ */
  /* Unconfirmed / worth more research (optional Appendix B)            */
  /* { id, title, detail, followUp }                                    */
  /* ------------------------------------------------------------------ */

  unconfirmed: [],
};
