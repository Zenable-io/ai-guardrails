/*
 * Loads the report template's app.js in a minimal DOM so its internals can be
 * unit-tested with the Node test runner and nothing else.
 *
 * No jsdom, no npm install: this repo ships a plugin, not a package, and keeps
 * `dependencies = []` to hold its supply-chain surface at zero. app.js touches
 * very little of the DOM at module scope, so a hand-written stub covering what
 * it actually uses is both sufficient and honest about the coupling — if a
 * future change reaches for a new DOM API at module scope, these tests fail
 * loudly rather than passing against a permissive fake.
 *
 * boot() is never allowed to run: readyState stays "loading", so app.js parks
 * itself on DOMContentLoaded and the tests get the pure functions without any
 * rendering side effects.
 */

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const APP_JS = path.join(__dirname, "..", "assets", "template", "app.js");

// A representative resolved block: exactly the shape fetch_chart_libs.py writes.
const DEFAULT_CHART_LIBS = {
  libs: [
    {
      global: "echarts",
      path: "report-assets/echarts-5.6.1.min.js",
      integrity: "sha384-" + "e".repeat(64),
    },
    {
      global: "mermaid",
      path: "report-assets/mermaid-11.15.0.min.js",
      integrity: "sha384-" + "m".repeat(64),
    },
  ],
};

/** A script element stub that records what app.js set on it. */
function makeScriptStub(onAppend) {
  const node = {
    tagName: "SCRIPT",
    src: "",
    async: false,
    onload: null,
    onerror: null,
    _attrs: {},
    setAttribute(k, v) {
      this._attrs[k] = v;
    },
  };
  node._append = () => onAppend(node);
  return node;
}

/**
 * Load app.js against `report` (the window.REPORT fixture).
 *
 * `loadScriptResult(url)` decides what a dynamic script load does: return an
 * object `{ ok, global }` to resolve (defining window[global] when ok), or
 * `{ ok: false }` to fire onerror. Every attempted load is recorded on
 * `env.loads` as `{ url, integrity, crossOrigin }`.
 */
function loadApp(report, options = {}) {
  const {
    protocol = "https:",
    loadScriptResult = () => ({ ok: false }),
    // What the resolve step wrote into the chart-libs-data block. The template
    // ships this as `null`; a real report always has it filled in.
    chartLibs = DEFAULT_CHART_LIBS,
  } = options;

  const loads = [];
  const warnings = [];
  const errors = [];

  const scriptEls = [];
  const onAppend = (node) => {
    const record = {
      url: node.src,
      integrity: node._attrs.integrity ?? node.integrity,
      crossOrigin: node._attrs.crossorigin ?? node.crossOrigin,
    };
    loads.push(record);
    // Resolve on a later turn, the way a real network load does, so awaiting
    // code in app.js is genuinely exercised rather than short-circuited.
    setImmediate(() => {
      const outcome = loadScriptResult(record.url) || { ok: false };
      if (outcome.ok) {
        if (outcome.global) window[outcome.global] = outcome.value ?? {};
        if (node.onload) node.onload();
      } else if (node.onerror) {
        node.onerror();
      }
    });
  };

  const noop = () => {};
  const nullQuery = () => null;
  const emptyQueryAll = () => [];

  const head = {
    appendChild(node) {
      scriptEls.push(node);
      if (node._append) node._append();
      return node;
    },
  };

  const document = {
    readyState: "loading", // keeps boot() parked on DOMContentLoaded
    head,
    documentElement: { dataset: {} },
    body: { classList: { contains: () => false, add: noop, remove: noop } },
    addEventListener: noop,
    removeEventListener: noop,
    getElementById: (id) =>
      id === "chart-libs-data"
        ? { textContent: chartLibs === null ? "null" : JSON.stringify(chartLibs) }
        : null,
    querySelector: nullQuery,
    querySelectorAll: emptyQueryAll,
    createElement(tag) {
      if (String(tag).toLowerCase() === "script") return makeScriptStub(onAppend);
      // Minimal element for el(); enough for footnotesListEl and friends.
      return {
        tagName: String(tag).toUpperCase(),
        className: "",
        innerHTML: "",
        textContent: "",
        children: [],
        dataset: {},
        _attrs: {},
        setAttribute(k, v) {
          this._attrs[k] = v;
        },
        getAttribute(k) {
          return this._attrs[k] ?? null;
        },
        removeAttribute(k) {
          delete this._attrs[k];
        },
        addEventListener: noop,
        appendChild(child) {
          this.children.push(child);
          return child;
        },
        querySelector: nullQuery,
        querySelectorAll: emptyQueryAll,
      };
    },
    createTextNode: (text) => ({ nodeType: 3, textContent: String(text) }),
  };

  let exported = null;
  const window = {
    REPORT: report,
    location: { protocol },
    matchMedia: () => ({ matches: false, addEventListener: noop }),
    addEventListener: noop,
    setTimeout,
    __ZENABLE_TEST_HOOK__: (api) => {
      exported = api;
    },
  };

  const sandbox = {
    window,
    document,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    setImmediate,
    console: {
      warn: (...args) => warnings.push(args.join(" ")),
      error: (...args) => errors.push(args.join(" ")),
      log: noop,
    },
  };
  sandbox.globalThis = sandbox;

  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(APP_JS, "utf8"), sandbox, { filename: APP_JS });

  if (!exported) {
    throw new Error("app.js did not call __ZENABLE_TEST_HOOK__ — seam missing?");
  }
  return { api: exported, window, document, loads, warnings, errors };
}

/** The smallest window.REPORT that lets app.js initialize. */
function minimalReport(overrides = {}) {
  return {
    findings: [],
    strengths: [],
    recommendations: [],
    attackPaths: null,
    ...overrides,
  };
}

module.exports = { loadApp, minimalReport, APP_JS, DEFAULT_CHART_LIBS };
