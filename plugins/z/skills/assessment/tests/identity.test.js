/*
 * Tests for the derived-identity model and the risk scoring behind it.
 *
 * The whole point of stable `key`s is that the F-NNN ids a reader sees are
 * positional and re-derive on every render. These tests pin that contract,
 * because a report that renumbers silently is worse than one that never did.
 */

const test = require("node:test");
const assert = require("node:assert/strict");

const { loadApp, minimalReport } = require("./harness");

const finding = (key, severity, extra = {}) => ({
  key,
  title: `Finding ${key}`,
  severity,
  likelihoodInputs: { exposure: 50, precondition: 50, discoverability: 50 },
  impactInputs: { scope: 50, sensitivity: 50, recoverability: 50 },
  ...extra,
});

test("findings are numbered by severity, not by source order", () => {
  const { api } = loadApp(
    minimalReport({
      findings: [finding("aaaa", "Low"), finding("bbbb", "Critical"), finding("cccc", "High")],
    }),
  );
  assert.deepEqual(
    Array.from(api.FINDINGS_ORDERED, (f) => [f.key, f._did]),
    [
      ["bbbb", "F-001"],
      ["cccc", "F-002"],
      ["aaaa", "F-003"],
    ],
  );
});

test("findings of equal severity order by impact x likelihood", () => {
  const { api } = loadApp(
    minimalReport({
      findings: [
        finding("lowscore", "High", {
          likelihoodInputs: { exposure: 10, precondition: 10, discoverability: 10 },
          impactInputs: { scope: 10, sensitivity: 10, recoverability: 10 },
        }),
        finding("highscore", "High", {
          likelihoodInputs: { exposure: 90, precondition: 90, discoverability: 90 },
          impactInputs: { scope: 90, sensitivity: 90, recoverability: 90 },
        }),
      ],
    }),
  );
  assert.deepEqual(Array.from(api.FINDINGS_ORDERED, (f) => f.key), [
    "highscore",
    "lowscore",
  ]);
});

test("inserting a finding renumbers the ones below it", () => {
  // This is the failure a hardcoded F-004 in prose produces: the number stays
  // put while the finding it named moves.
  const before = loadApp(minimalReport({ findings: [finding("x", "High"), finding("y", "Low")] }));
  assert.equal(before.api.didForKey("y"), "F-002");

  const after = loadApp(
    minimalReport({
      findings: [finding("x", "High"), finding("y", "Low"), finding("z", "Critical")],
    }),
  );
  assert.equal(after.api.didForKey("z"), "F-001");
  assert.equal(after.api.didForKey("y"), "F-003");
});

test("strengths, recommendations and attack paths number by source order", () => {
  const { api } = loadApp(
    minimalReport({
      strengths: [{ key: "s1", title: "A" }, { key: "s2", title: "B" }],
      recommendations: [{ key: "r1", title: "R" }],
      attackPaths: { paths: [{ key: "p1", title: "P" }, { key: "p2", title: "Q" }] },
    }),
  );
  assert.deepEqual(Array.from(api.STRENGTHS_ORDERED, (s) => s._did), ["S-001", "S-002"]);
  assert.deepEqual(Array.from(api.RECS_ORDERED, (r) => r._did), ["REC-01"]);
  assert.deepEqual(Array.from(api.ATTACKS_ORDERED, (p) => p._did), ["AP-1", "AP-2"]);
});

test("severity aliases normalize to the four canonical levels", () => {
  const { api } = loadApp(minimalReport());
  const cases = {
    Critical: ["critical", "CRIT", "blocker"],
    High: ["high", "ERROR", "severe"],
    Medium: ["moderate", "warn", "MED"],
    Low: ["info", "informational", "note"],
  };
  for (const [expected, aliases] of Object.entries(cases)) {
    for (const alias of aliases) {
      assert.equal(api.normalizeFindingSeverity(alias), expected, alias);
    }
  }
  // An unrecognised value is preserved rather than silently downgraded.
  assert.equal(api.normalizeFindingSeverity("Catastrophic"), "Catastrophic");
});

test("likelihood is weighted 0.5/0.3/0.2 and missing inputs default to 50", () => {
  const { api } = loadApp(minimalReport());
  assert.equal(
    api.likelihoodScoreOf({
      likelihoodInputs: { exposure: 100, precondition: 0, discoverability: 0 },
    }),
    50,
  );
  assert.equal(api.likelihoodScoreOf({}), 50);
  assert.equal(api.likelihoodScoreOf({ likelihoodInputs: { exposure: 100 } }), 75);
});

test("impact averages only the inputs that are present", () => {
  const { api } = loadApp(minimalReport());
  assert.equal(api.impactScoreOf({ impactInputs: { scope: 90, sensitivity: 30 } }), 60);
  assert.equal(api.impactScoreOf({ impactInputs: {} }), 50);
});

test("risk buckets split at the thirds", () => {
  const { api } = loadApp(minimalReport());
  assert.equal(api.bucketOf(0), "Low");
  assert.equal(api.bucketOf(33.32), "Low");
  assert.equal(api.bucketOf(100 / 3), "Moderate");
  assert.equal(api.bucketOf(66.66), "Moderate");
  assert.equal(api.bucketOf(200 / 3), "High");
  assert.equal(api.zoneOf(90, 90), "high");
  assert.equal(api.zoneOf(10, 10), "low");
  assert.equal(api.zoneOf(90, 10), "moderate");
});

test("CVSS scores map to the standard severity bands", () => {
  const { api } = loadApp(minimalReport());
  assert.equal(api.severityFromCvss(9.0), "Critical");
  assert.equal(api.severityFromCvss(8.9), "High");
  assert.equal(api.severityFromCvss(7.0), "High");
  assert.equal(api.severityFromCvss(6.9), "Medium");
  assert.equal(api.severityFromCvss(3.9), "Low");
});

test("hardcoded display ids are detected in any authored field", () => {
  const { api } = loadApp(minimalReport());
  const hits = api.findLiteralDisplayIds({
    takeaways: ["F-004 committed keys"],
    trustBoundary: { mermaid: "A -->|see REC-01| B" },
    nested: [{ deep: { detail: "chains AP-3 and S-002" } }],
  });
  assert.deepEqual(new Set(Array.from(hits)), new Set(["F-004", "REC-01", "AP-3", "S-002"]));
});

test("the derived _did values do not count as hardcoded ids", () => {
  // FINDINGS_ORDERED stamps _did onto the same objects window.REPORT holds, so
  // a naive scan would report every finding as an offender.
  const { api, warnings } = loadApp(
    minimalReport({ findings: [finding("aaaa", "High")] }),
  );
  assert.deepEqual(Array.from(api.findLiteralDisplayIds(api.FINDINGS_ORDERED)), []);
  assert.deepEqual(warnings, []);
});

test("[[key]] cross-refs are not flagged as hardcoded ids", () => {
  const { api } = loadApp(minimalReport());
  assert.deepEqual(Array.from(api.findLiteralDisplayIds({ t: "see [[k3f9wq]]" })), []);
});
