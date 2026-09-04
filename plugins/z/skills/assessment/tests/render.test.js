/*
 * Tests for the report template's markdown/prose pipeline.
 *
 * These cover the rendering the report walkthrough depends on: every one of
 * them corresponds to something that shipped wrong in a real assessment.
 */

const test = require("node:test");
const assert = require("node:assert/strict");

const { loadApp, minimalReport } = require("./harness");

const FIXTURE = minimalReport({
  findings: [
    {
      key: "k1aaaa",
      title: "Committed credentials",
      severity: "Critical",
      likelihoodInputs: { exposure: 90, precondition: 95, discoverability: 95 },
      impactInputs: { scope: 90, sensitivity: 95, recoverability: 95 },
    },
    {
      key: "k2bbbb",
      title: "Unauthenticated webhook",
      severity: "High",
      likelihoodInputs: { exposure: 60, precondition: 40, discoverability: 50 },
      impactInputs: { scope: 55, sensitivity: 25, recoverability: 25 },
    },
  ],
  recommendations: [{ key: "r1eeee", title: "Rotate", relatedFindingKeys: ["k1aaaa"] }],
  strengths: [{ key: "s1dddd", title: "CI on every PR" }],
});

const { api } = loadApp(FIXTURE);

test("renderInline renders code spans, bold and external links", () => {
  const html = api.renderInline("Set `FOO` to **bar** per [docs](https://x.test/d)", []);
  assert.match(html, /<code>FOO<\/code>/);
  assert.match(html, /<strong>bar<\/strong>/);
  assert.match(html, /<a href="https:\/\/x\.test\/d" target="_blank" rel="noopener">docs<\/a>/);
});

test("renderInline escapes HTML in authored prose", () => {
  // Report data quotes source from the assessed repo, which is untrusted input.
  const html = api.renderInline('<img src=x onerror="alert(1)">', []);
  assert.ok(!html.includes("<img"));
  assert.match(html, /&lt;img/);
});

test("renderInline footnotes bare URLs and reuses one number per URL", () => {
  const footnotes = [];
  const html = api.renderInline(
    "See https://x.test/a and https://x.test/b and https://x.test/a again",
    footnotes,
  );
  assert.deepEqual(footnotes, ["https://x.test/a", "https://x.test/b"]);
  assert.equal((html.match(/fn-ref/g) || []).length, 3);
  assert.match(html, /href="#fn-1"/);
  assert.match(html, /href="#fn-2"/);
});

test("renderInline trailing punctuation stays outside the footnoted URL", () => {
  const footnotes = [];
  api.renderInline("Documented at https://x.test/page.", footnotes);
  assert.deepEqual(footnotes, ["https://x.test/page"]);
});

test("renderInline resolves [[key]] cross-refs to the derived display id", () => {
  const html = api.renderInline("Rotate the keys in [[k1aaaa]]", []);
  assert.match(html, /href="#finding-F-001"/);
  assert.match(html, />F-001</);
  assert.match(html, /title="F-001: Committed credentials"/);
});

test("renderInline leaves an unresolvable [[key]] visible rather than silently dropping it", () => {
  assert.match(api.renderInline("see [[nosuch]]", []), /\[\[nosuch\]\]/);
});

test("renderInline rejects download paths that try to escape the bundle", () => {
  for (const bad of ["../secrets", "a/../../b", "a\\b", "a//b"]) {
    const html = api.renderInline(`[x](download:evidence/${bad})`, []);
    assert.ok(!html.includes("data-download-path"), `accepted ${bad}`);
  }
  const okHtml = api.renderInline("[x](download:evidence/scan/out.json)", []);
  assert.match(okHtml, /data-download-path="scan\/out\.json"/);
  assert.match(okHtml, /data-download-kind="evidence"/);
});

test("renderProse splits paragraphs, bullets and subheads", () => {
  const html = api.renderProse("One.\n\n#### Why\n\n- a\n- b", []);
  assert.match(html, /<p>One\.<\/p>/);
  assert.match(html, /<h4 class="finding-subhead">Why<\/h4>/);
  assert.match(html, /<ul class="finding-list"><li>a<\/li><li>b<\/li><\/ul>/);
});

test("renderProse renders a GFM pipe table", () => {
  // Regression: authored evidence tables used to collapse into one run-on
  // paragraph with the |---|---| separator rendered as literal text.
  const html = api.renderProse(
    "| File | Credential |\n|---|---|\n| `.env` | AWS key |\n| `k.json` | GCP key |",
    [],
  );
  assert.match(html, /<table class="prose-table">/);
  assert.match(html, /<thead><tr><th>File<\/th><th>Credential<\/th><\/tr><\/thead>/);
  assert.equal((html.match(/<tr>/g) || []).length, 3); // header + 2 body rows
  assert.match(html, /<td><code>\.env<\/code><\/td>/);
  assert.ok(!html.includes("---"));
});

test("renderProse table honours alignment markers", () => {
  const html = api.renderProse("| a | b | c |\n|:--|:-:|--:|\n| 1 | 2 | 3 |", []);
  assert.match(html, /<th style="text-align:left">a<\/th>/);
  assert.match(html, /<th style="text-align:center">b<\/th>/);
  assert.match(html, /<th style="text-align:right">c<\/th>/);
});

test("renderProse pads a short table row instead of shifting columns", () => {
  const html = api.renderProse("| a | b | c |\n|---|---|---|\n| 1 |", []);
  const body = html.split("<tbody>")[1];
  assert.equal((body.match(/<td/g) || []).length, 3);
});

test("renderProse leaves a pipe in prose alone without a separator row", () => {
  const html = api.renderProse("Run `a | b` to filter.", []);
  assert.ok(!html.includes("<table"));
  assert.match(html, /<p>/);
});

// app.js runs in a vm context, so the arrays it returns have that realm's
// Array prototype and deepStrictEqual rejects them on identity alone. Copy into
// a host array before comparing — the values are what matter here.
const plain = (value) => (value == null ? value : Array.from(value));

test("splitTableRow honours escaped pipes", () => {
  assert.deepEqual(plain(api.splitTableRow("| a \\| b | c |")), ["a | b", "c"]);
});

test("tableAlignments only accepts a real separator row", () => {
  assert.deepEqual(plain(api.tableAlignments("|---|---|")), ["", ""]);
  assert.equal(api.tableAlignments("| a | b |"), null);
  assert.equal(api.tableAlignments("no pipes here"), null);
  assert.equal(api.tableAlignments("|---| b |"), null);
  // GFM allows a single dash, and colons set alignment.
  assert.deepEqual(plain(api.tableAlignments("| - | :-: |")), ["", "center"]);
});

test("table cells run through the inline pipeline", () => {
  const footnotes = [];
  const html = api.renderProse(
    "| Item | Ref |\n|---|---|\n| **bold** | [[k2bbbb]] |",
    footnotes,
  );
  assert.match(html, /<strong>bold<\/strong>/);
  assert.match(html, /href="#finding-F-002"/);
});
