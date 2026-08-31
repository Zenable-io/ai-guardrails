/*
 * Tests for how the report loads its two remote dependencies.
 *
 * These are the rules that decide whether a report renders its charts at all:
 * where the bytes come from, whether SRI is enforced, and whether the pinned
 * URL stays visible to the tooling that decides which versions to keep.
 */

const test = require("node:test");
const assert = require("node:assert/strict");

const { loadApp, minimalReport } = require("./harness");

const ASSET_PATH_RE = /^report-assets\/[A-Za-z0-9_]+-\d+\.\d+\.\d+\.min\.js$/;

test("a resolved report exposes a sha384 SRI and a versioned path per lib", () => {
  const { api } = loadApp(minimalReport());
  const libs = Array.from(api.CHART_LIBS);
  assert.ok(libs.length >= 2);
  for (const lib of libs) {
    assert.match(lib.integrity, /^sha384-[A-Za-z0-9+/]+=*$/, lib.global);
    assert.match(lib.path, ASSET_PATH_RE, lib.global);
  }
});

test("the template carries no pin of its own", () => {
  // The producer cannot know which version the app serves, and a hand-copied
  // hash that falls behind fails as a browser-blocked script. The version and
  // integrity are resolved at build time and written into chart-libs-data.
  const source = require("node:fs").readFileSync(require("./harness").APP_JS, "utf8");
  assert.ok(!source.includes("sha384-"), "app.js must not carry an SRI pin");
  assert.ok(!/echarts-\d/.test(source), "app.js must not name an asset version");
});

test("an unresolved report degrades instead of throwing", () => {
  // chart-libs-data ships as null; build_report.py refuses to bundle in that
  // state, but a half-built workspace opened locally must still hydrate.
  const { api } = loadApp(minimalReport(), { chartLibs: null });
  assert.deepEqual(Array.from(api.CHART_LIBS), []);
});

test("the resolved path is used verbatim, never reassembled", () => {
  // Retention tooling finds a report's version by matching this exact shape in
  // the emitted HTML. If the loader rebuilt the URL from a bare filename the
  // string would not be there, the version would look unreferenced, and
  // removing it would 404 every report already pinned to it.
  const chartLibs = {
    libs: [
      {
        global: "echarts",
        path: "report-assets/echarts-9.9.9.min.js",
        integrity: "sha384-zzz",
      },
    ],
  };
  const { api, loads } = loadApp(minimalReport(), { chartLibs });
  const lib = Array.from(api.CHART_LIBS)[0];
  assert.match(lib.path, ASSET_PATH_RE);
  return api.loadChartLib(lib).then(() => {
    assert.equal(loads[0].url, "/report-assets/echarts-9.9.9.min.js");
  });
});

test("a hosted report loads same-origin with SRI enforced", async () => {
  const { api, loads } = loadApp(minimalReport(), {
    protocol: "https:",
    loadScriptResult: () => ({ ok: true, global: "echarts" }),
  });
  const lib = Array.from(api.CHART_LIBS)[0];
  assert.equal(await api.loadChartLib(lib), true);

  assert.equal(loads.length, 1, "hosted should not need a fallback");
  assert.equal(loads[0].url, `/${lib.path}`);
  assert.equal(loads[0].integrity, lib.integrity);
  assert.equal(loads[0].crossOrigin, "anonymous");
});

test("a file:// report reads the vendored copy without SRI", async () => {
  // SRI cannot be satisfied for an opaque file:// response — setting integrity
  // there makes the browser block the script instead of degrading, which is
  // what left local review with no charts at all.
  const { api, loads } = loadApp(minimalReport(), {
    protocol: "file:",
    loadScriptResult: () => ({ ok: true, global: "echarts" }),
  });
  const lib = Array.from(api.CHART_LIBS)[0];
  assert.equal(await api.loadChartLib(lib), true);

  assert.equal(loads.length, 1);
  assert.equal(loads[0].url, lib.path, "must be relative, not root-relative");
  assert.equal(loads[0].integrity, undefined);
  assert.equal(loads[0].crossOrigin, undefined);
});

test("file:// never attempts the root-relative path", async () => {
  // It resolves to file:///report-assets/… and is rejected cross-origin,
  // printing CORS errors into the console of the review it exists to serve.
  const { api, loads } = loadApp(minimalReport(), {
    protocol: "file:",
    loadScriptResult: () => ({ ok: false }),
  });
  await api.loadChartLib(Array.from(api.CHART_LIBS)[0]);
  assert.ok(!loads.some((l) => l.url.startsWith("/report-assets/")), JSON.stringify(loads));
});

test("a failed first attempt falls back to the pinned absolute URL with SRI", async () => {
  const { api, loads } = loadApp(minimalReport(), {
    protocol: "file:",
    loadScriptResult: (url) =>
      url.startsWith("https://") ? { ok: true, global: "echarts" } : { ok: false },
  });
  const lib = Array.from(api.CHART_LIBS)[0];
  assert.equal(await api.loadChartLib(lib), true);

  assert.equal(loads.length, 2);
  assert.equal(loads[1].url, `https://www.zenable.app/${lib.path}`);
  assert.equal(loads[1].integrity, lib.integrity, "SRI must hold over the network");
});

test("the fallback honours a stamped environment subdomain", async () => {
  const { api, window, loads } = loadApp(minimalReport(), {
    protocol: "file:",
    loadScriptResult: (url) =>
      url.startsWith("https://") ? { ok: true, global: "echarts" } : { ok: false },
  });
  window.__ZENABLE_SUBDOMAIN__ = "staging";
  const lib = Array.from(api.CHART_LIBS)[0];
  await api.loadChartLib(lib);
  assert.equal(loads[1].url, `https://staging.zenable.app/${lib.path}`);
});

test("an already-present global short-circuits the load entirely", async () => {
  const { api, window, loads } = loadApp(minimalReport());
  window.echarts = {};
  assert.equal(await api.loadChartLib(Array.from(api.CHART_LIBS)[0]), true);
  assert.deepEqual(loads, []);
});

test("loadChartLib resolves false rather than throwing when every source fails", async () => {
  // The report must still hydrate chart-less; a rejection here would abort boot.
  const { api } = loadApp(minimalReport(), {
    protocol: "https:",
    loadScriptResult: () => ({ ok: false }),
  });
  assert.equal(await api.loadChartLib(Array.from(api.CHART_LIBS)[0]), false);
});
