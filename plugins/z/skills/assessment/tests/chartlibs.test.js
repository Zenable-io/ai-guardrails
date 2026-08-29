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

test("every pinned lib declares a sha384 SRI and a versioned path", () => {
  const { api } = loadApp(minimalReport());
  const libs = Array.from(api.CHART_LIBS);
  assert.ok(libs.length >= 2);
  for (const lib of libs) {
    assert.match(lib.integrity, /^sha384-[A-Za-z0-9+/]+=*$/, lib.global);
    assert.match(lib.path, ASSET_PATH_RE, lib.global);
  }
});

test("the versioned path is one literal string, not assembled at use", () => {
  // Retention tooling decides which asset versions are still needed by scanning
  // issued report.html files for this exact shape. If the URL were built from a
  // bare filename the scan would find nothing, the version would look
  // unreferenced, and removing it would 404 every report already pinned to it.
  const source = require("node:fs").readFileSync(require("./harness").APP_JS, "utf8");
  const { api } = loadApp(minimalReport());
  for (const lib of Array.from(api.CHART_LIBS)) {
    assert.ok(
      source.includes(`"${lib.path}"`),
      `${lib.global}: ${lib.path} must appear verbatim in app.js`,
    );
    assert.match(lib.path, ASSET_PATH_RE);
  }
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
