/*
 * Tests for the report template's stylesheet.
 *
 * Like render.test.js, every case here corresponds to something that shipped
 * wrong in a real assessment. The report is authored once per engagement and
 * reviewed by eye exactly once, so a layout rule that only looks right at a
 * particular item count fails silently and late.
 *
 * These read styles.css as text rather than laying the page out in a browser:
 * the repo ships a plugin with `dependencies = []` and no headless browser, and
 * the invariants worth protecting here are properties of the declarations
 * themselves.
 */

const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");

const TEMPLATE = path.join(__dirname, "..", "assets", "template");
const CSS = fs.readFileSync(path.join(TEMPLATE, "styles.css"), "utf8");
const HTML = fs.readFileSync(path.join(TEMPLATE, "index.html"), "utf8");

/*
 * Containers app.js fills from a `window.REPORT` array, so their child count is
 * whatever the engagement produced — commonly one. Each entry is the element id
 * app.js writes into, plus the class carrying its layout.
 *
 * This list is maintained by hand. `every data-driven container id exists in
 * index.html with its expected class` below fails if an id or class is renamed,
 * so it cannot rot silently into a test that checks nothing.
 */
const DATA_DRIVEN_CONTAINERS = [
  { id: "findingsList", className: "findings-list", source: "findings" },
  { id: "strengthsList", className: "strengths-list", source: "strengths" },
  { id: "recsList", className: "recs-list", source: "recommendations" },
  { id: "cvesList", className: "cves-list", source: "cves" },
  {
    id: "customRequirementsList",
    className: "tokenization-list",
    source: "customRequirements.sections",
  },
  { id: "unconfirmedList", className: "unconfirmed-list", source: "unconfirmed" },
  { id: "attackList", className: "attack-list", source: "attackPaths.paths" },
  { id: "repoSummaryCards", className: "metrics-cards", source: "metrics summary" },
  { id: "severityChips", className: "severity-chips", source: "derived severity counts" },
];

/**
 * Value of `prop` in the rule whose selector list contains exactly `selector`,
 * or null when the rule does not set it.
 *
 * Deliberately simple: styles.css is hand-written, flat, and free of nested
 * at-rules around these selectors. A CSS parser would be a dependency.
 */
function declaration(selector, prop) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const rule = new RegExp(
    `(^|[,}])\\s*${escaped}\\s*(,[^{]*)?\\{([^}]*)\\}`,
    "m",
  );
  const match = CSS.match(rule);
  if (!match) return null;
  const body = match[3];
  const decl = body.match(new RegExp(`(?:^|;)\\s*${prop}\\s*:([^;]*)`));
  return decl ? decl[1].trim() : null;
}

/**
 * Split a grid-template-columns value into top-level tracks, treating a
 * `repeat(...)` / `minmax(...)` call as one unit so its internal commas do not
 * read as track separators.
 */
function tracks(value) {
  const out = [];
  let depth = 0;
  let current = "";
  for (const ch of value) {
    if (ch === "(") depth += 1;
    if (ch === ")") depth -= 1;
    if (ch === " " && depth === 0) {
      if (current) out.push(current);
      current = "";
      continue;
    }
    current += ch;
  }
  if (current) out.push(current);
  return out;
}

test("every data-driven container id exists in index.html with its expected class", () => {
  for (const { id, className } of DATA_DRIVEN_CONTAINERS) {
    const el = HTML.match(new RegExp(`<[^>]*id="${id}"[^>]*>`));
    assert.ok(el, `#${id} is missing from index.html — update DATA_DRIVEN_CONTAINERS`);
    assert.match(
      el[0],
      new RegExp(`class="[^"]*\\b${className}\\b[^"]*"`),
      `#${id} no longer carries .${className} — update DATA_DRIVEN_CONTAINERS`,
    );
  }
});

test("a data-driven grid never hardcodes a fixed number of columns", () => {
  /*
   * A container holding N cards from data.js must lay out correctly for N = 1.
   * `grid-template-columns: 1fr 1fr` reserves the second track whether or not
   * anything fills it, so a report with a single custom requirement rendered
   * that card at half width with dead space beside it. `repeat(auto-fit, ...)`
   * collapses the empty track and the lone card fills the row.
   */
  for (const { className, source } of DATA_DRIVEN_CONTAINERS) {
    const value = declaration(`.${className}`, "grid-template-columns");
    if (value === null) continue; // not a grid, or inherits — nothing to assert

    const parsed = tracks(value);
    if (parsed.length === 1 && /^repeat\(auto-(fit|fill),/.test(parsed[0])) continue;
    if (parsed.length === 1) continue; // a single track is full width by definition

    assert.fail(
      `.${className} (populated from ${source}) declares ` +
        `grid-template-columns: ${value} — ${parsed.length} fixed tracks. ` +
        `A single item would render at 1/${parsed.length} width. ` +
        `Use repeat(auto-fit, minmax(<min>, 1fr)) so the row collapses.`,
    );
  }
});

test("a fixed two-column grid is still allowed where both children always exist", () => {
  /*
   * The guard above must not overreach. .scope-grid holds exactly two authored
   * children — In Scope and Out of Scope — which are always both present, so a
   * fixed 1fr 1fr is correct there and should keep working.
   */
  const value = declaration(".scope-grid", "grid-template-columns");
  assert.equal(value, "1fr 1fr");
  assert.equal(tracks(value).length, 2);
});
