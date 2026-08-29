/*
 * Render & interactivity for the code-review report template.
 * Pure DOM; no build step. data.js exposes window.REPORT.
 */

(function () {
  "use strict";
  const R = window.REPORT;
  if (!R) {
    console.error("REPORT data missing");
    return;
  }

  // ---------- helpers --------------------------------------------------------

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // Linkchips stopPropagation so a chip click doesn't toggle the finding card —
  // but that also stops the document-level scroll handler, so each chip must
  // navigate in-page itself. preventDefault avoids the srcdoc frame's native
  // #anchor navigation (which hits the parent's X-Frame-Options: DENY).
  function linkChipNav(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const href = ev.currentTarget.getAttribute("href") || "";
    if (href.startsWith("#finding-")) {
      jumpToFinding(href.slice("#finding-".length));
      return;
    }
    if (href.length > 1 && href.startsWith("#")) {
      const target = document.getElementById(decodeURIComponent(href.slice(1)));
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "html") node.innerHTML = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on") && typeof v === "function") {
        node.addEventListener(k.slice(2).toLowerCase(), v);
      } else if (k === "dataset") {
        for (const [dk, dv] of Object.entries(v)) node.dataset[dk] = dv;
      } else {
        node.setAttribute(k, v);
      }
    }
    for (const c of [].concat(children)) {
      if (c == null || c === false) continue;
      node.appendChild(c.nodeType ? c : document.createTextNode(c));
    }
    return node;
  }

  function path(obj, dotted) {
    return dotted.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
  }

  // ---------- Light markdown for finding/evidence prose ---------------------
  // Supports: `code` → <code>, [label](download:kind/path), and http(s) URLs →
  // numbered footnote refs that show the full URL on hover (HTML) and print.
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
  function cleanDownloadPath(path) {
    const raw = String(path || "").trim();
    if (!raw || raw.includes("\\")) return "";
    const parts = raw.split("/");
    if (
      parts.some(
        (part) => !part || part === "." || part === ".." || part.includes("\0"),
      )
    ) {
      return "";
    }
    return parts.join("/");
  }
  // ---------- Stable keys → derived, human-friendly display ids -------------
  // The data carries opaque stable `key`s; the F-NNN / S-NNN / REC-NN / AP-N
  // ids readers see are DERIVED here at render time and never stored. Findings
  // order by severity then impact×likelihood, so editing a score or severity
  // renumbers everything automatically; strengths, recommendations and attack
  // paths number by source order. Every cross-ref in prose is a [[key]] token
  // resolved back to the live id (and link) through these maps.
  function normalizeFindingSeverity(severity) {
    const raw = String(severity || "").trim();
    const key = raw.toLowerCase();
    if (["crit", "critical", "blocker"].includes(key)) return "Critical";
    if (["hi", "high", "error", "severe"].includes(key)) return "High";
    if (["medium", "moderate", "med", "warning", "warn"].includes(key)) return "Medium";
    if (["low", "info", "informational", "note"].includes(key)) return "Low";
    return raw || "Medium";
  }
  const SEV_RANK = { Critical: 0, High: 1, Medium: 2, Low: 3 };
  function likelihoodOf(f) {
    const i = f.likelihoodInputs || {};
    return (
      0.5 * (i.exposure ?? 50) +
      0.3 * (i.precondition ?? 50) +
      0.2 * (i.discoverability ?? 50)
    );
  }
  function impactOf(f) {
    const i = f.impactInputs || {};
    const v = [i.scope, i.sensitivity, i.recoverability].filter((x) => x != null);
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : 50;
  }
  const FINDINGS_ORDERED = (R.findings || [])
    .map((f, i) => ({
      f,
      i,
      s: SEV_RANK[normalizeFindingSeverity(f.severity)] ?? 9,
      sc: likelihoodOf(f) * impactOf(f),
    }))
    .sort((a, b) => a.s - b.s || b.sc - a.sc || a.i - b.i)
    .map((x, n) => ((x.f._did = `F-${String(n + 1).padStart(3, "0")}`), x.f));
  const STRENGTHS_ORDERED = (R.strengths || []).map(
    (s, n) => ((s._did = `S-${String(n + 1).padStart(3, "0")}`), s),
  );
  const RECS_ORDERED = (R.recommendations || []).map(
    (r, n) => ((r._did = `REC-${String(n + 1).padStart(2, "0")}`), r),
  );
  const ATTACKS_ORDERED = ((R.attackPaths && R.attackPaths.paths) || []).map(
    (p, n) => ((p._did = `AP-${n + 1}`), p),
  );
  const FINDING_BY_KEY = new Map(FINDINGS_ORDERED.map((f) => [f.key, f]));
  const STRENGTH_BY_KEY = new Map(STRENGTHS_ORDERED.map((s) => [s.key, s]));
  const REC_BY_KEY = new Map(RECS_ORDERED.map((r) => [r.key, r]));
  const ATTACK_BY_KEY = new Map(ATTACKS_ORDERED.map((p) => [p.key, p]));
  const REF_BY_KEY = new Map();
  for (const f of FINDINGS_ORDERED)
    REF_BY_KEY.set(f.key, {
      did: f._did,
      anchor: `finding-${f._did}`,
      title: `${f._did}: ${f.title}`,
    });
  for (const s of STRENGTHS_ORDERED)
    REF_BY_KEY.set(s.key, {
      did: s._did,
      anchor: `strength-${s._did}`,
      title: `${s._did}: ${s.title}`,
    });
  for (const r of RECS_ORDERED)
    REF_BY_KEY.set(r.key, {
      did: r._did,
      anchor: `rec-${r._did}`,
      title: `${r._did}: ${r.title}`,
    });
  for (const p of ATTACKS_ORDERED)
    REF_BY_KEY.set(p.key, {
      did: p._did,
      anchor: `attack-${p._did}`,
      title: p.title ? `${p._did}: ${p.title}` : p._did,
    });
  // Display ids are DERIVED, so any literal `F-004` typed into authored prose
  // or into the mermaid source silently rots the moment a finding is added,
  // rescored, or reordered — the text keeps pointing at a slot number that now
  // belongs to a different finding. Nothing at render time can tell a stale
  // literal from a correct one, so flag every literal and let the author
  // replace it with the `[[key]]` cross-ref that renumbers itself.
  // build_report.py enforces the same rule as a hard failure at bundle time.
  const LITERAL_DID_RE = /\b(?:F-\d{3}|S-\d{3}|REC-\d{2}|AP-\d+)\b/g;
  function findLiteralDisplayIds(data) {
    // `_did` is injected above, so drop it — otherwise every finding reports
    // itself. Authored data is what we are auditing.
    const authored = JSON.stringify(data, (k, v) => (k === "_did" ? undefined : v));
    return Array.from(new Set(String(authored).match(LITERAL_DID_RE) || []));
  }
  function warnLiteralDisplayIds() {
    const hits = findLiteralDisplayIds(R);
    if (!hits.length) return;
    console.warn(
      "[zenable-assessment] hardcoded display ids in authored data: " +
        hits.join(", ") +
        ". These do not follow renumbering — replace each with the [[key]] " +
        "cross-ref of the item it points at.",
    );
  }
  const didForKey = (k) => (REF_BY_KEY.get(k) || {}).did || k;
  const refTitle = (k) => (REF_BY_KEY.get(k) || {}).title || k;
  const token = (kind, i) => `\uE000${kind}${i}\uE001`;

  function renderInline(text, footnotes) {
    const codeSlots = [];
    const downloadSlots = [];
    const extlinkSlots = [];
    let s = String(text).replace(/`([^`\n]+)`/g, (_, code) => {
      const i = codeSlots.length;
      codeSlots.push(code);
      return token("C", i);
    });
    s = s.replace(
      /\[([^\]\n]+)\]\(download:(context|evidence|experiment)\/([^)]+)\)/g,
      (_, label, kind, rawPath) => {
        const path = cleanDownloadPath(rawPath);
        if (!path) return label;
        const i = downloadSlots.length;
        downloadSlots.push({ label, kind, path });
        return token("D", i);
      },
    );
    // External markdown links: [label](https://…) → a titled new-tab link.
    // Must run before the bare-URL pass below so the URL isn't also footnoted.
    s = s.replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g, (_, label, url) => {
      const i = extlinkSlots.length;
      extlinkSlots.push({ label, url });
      return token("L", i);
    });
    s = s.replace(/https?:\/\/[^\s<>"'`)]+/g, (url) => {
      const m = url.match(/^(.*?)([.,;:)\]]+)$/);
      const clean = m ? m[1] : url;
      const tail = m ? m[2] : "";
      let i = footnotes.indexOf(clean);
      if (i === -1) {
        footnotes.push(clean);
        i = footnotes.length - 1;
      }
      return `${token("U", i)}${tail}`;
    });
    s = escapeHtml(s);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // [[key]] cross-refs → live display id (F-NNN / S-NNN / REC-NN / AP-N) + link.
    s = s.replace(/\[\[([a-z0-9]{4,8})\]\]/g, (m, key) => {
      const ref = REF_BY_KEY.get(key);
      if (!ref) return m;
      return `<a class="finding-ref" href="#${ref.anchor}" title="${escapeHtml(ref.title)}">${escapeHtml(ref.did)}</a>`;
    });
    s = s.replace(
      /\uE000C(\d+)\uE001/g,
      (_, i) => `<code>${escapeHtml(codeSlots[+i])}</code>`,
    );
    s = s.replace(/\uE000D(\d+)\uE001/g, (_, i) => {
      const item = downloadSlots[+i];
      if (!item) return "";
      return (
        `<a href="#" data-download-kind="${escapeHtml(item.kind)}" ` +
        `data-download-path="${escapeHtml(item.path)}">${escapeHtml(item.label)}</a>`
      );
    });
    s = s.replace(/\uE000L(\d+)\uE001/g, (_, i) => {
      const item = extlinkSlots[+i];
      if (!item) return "";
      return `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener">${escapeHtml(item.label)}</a>`;
    });
    s = s.replace(/\uE000U(\d+)\uE001/g, (_, i) => {
      const n = +i + 1,
        url = footnotes[+i];
      const safe = escapeHtml(url);
      return `<sup class="fn-ref"><a href="#fn-${n}" data-href="${safe}" title="${safe}">[${n}]</a></sup>`;
    });
    return s;
  }
  // ---------- GFM pipe tables in prose --------------------------------------
  // Authored findings routinely tabulate evidence (file / credential / identity
  // rows). Without a table pass every row collapsed into one run-on paragraph
  // with the `|---|---|` separator rendered as literal text.
  function splitTableRow(line) {
    const s = line.trim().replace(/^\|/, "").replace(/\|$/, "");
    const cells = [];
    let cur = "";
    for (let i = 0; i < s.length; i++) {
      if (s[i] === "\\" && s[i + 1] === "|") {
        cur += "|";
        i++;
        continue;
      }
      if (s[i] === "|") {
        cells.push(cur.trim());
        cur = "";
        continue;
      }
      cur += s[i];
    }
    cells.push(cur.trim());
    return cells;
  }
  // A separator row is what distinguishes a table from prose that merely
  // contains a pipe, so require it: every cell must be `---`, `:--`, or `--:`.
  function tableAlignments(line) {
    if (line.indexOf("|") === -1) return null;
    const cells = splitTableRow(line);
    if (!cells.length) return null;
    const aligns = [];
    for (const cell of cells) {
      // GFM allows one or more dashes, so `:-:` is a legal centre marker — an
      // over-strict `-{2,}` silently demoted the whole table back to prose.
      const m = cell.match(/^(:?)-+(:?)$/);
      if (!m) return null;
      aligns.push(
        m[1] && m[2] ? "center" : m[2] ? "right" : m[1] ? "left" : "",
      );
    }
    return aligns;
  }
  function renderTableRow(tag, cells, aligns, footnotes) {
    const tds = cells.map((cell, i) => {
      const align = aligns[i] ? ` style="text-align:${aligns[i]}"` : "";
      return `<${tag}${align}>${renderInline(cell, footnotes)}</${tag}>`;
    });
    return `<tr>${tds.join("")}</tr>`;
  }

  function renderProse(text, footnotes) {
    const out = [];
    for (const block of String(text || "").split(/\n\n+/)) {
      const lines = block.split("\n");
      let para = [];
      const flush = () => {
        if (para.length) {
          out.push(`<p>${renderInline(para.join(" "), footnotes)}</p>`);
          para = [];
        }
      };
      let k = 0;
      while (k < lines.length) {
        const line = lines[k];
        const h = line.match(/^####\s+(.+)$/);
        if (h) {
          flush();
          out.push(`<h4 class="finding-subhead">${renderInline(h[1], footnotes)}</h4>`);
          k++;
          continue;
        }
        const aligns =
          line.indexOf("|") !== -1 && k + 1 < lines.length
            ? tableAlignments(lines[k + 1])
            : null;
        if (aligns) {
          flush();
          const header = splitTableRow(line);
          const rows = [];
          k += 2;
          while (k < lines.length && lines[k].indexOf("|") !== -1) {
            rows.push(splitTableRow(lines[k]));
            k++;
          }
          // Pad/truncate body rows to the header width so a short row can't
          // shift the remaining cells into the wrong columns.
          const body = rows.map((r) => {
            const cells = r.slice(0, header.length);
            while (cells.length < header.length) cells.push("");
            return renderTableRow("td", cells, aligns, footnotes);
          });
          out.push(
            `<div class="prose-table-wrap"><table class="prose-table">` +
              `<thead>${renderTableRow("th", header, aligns, footnotes)}</thead>` +
              `<tbody>${body.join("")}</tbody></table></div>`,
          );
          continue;
        }
        if (/^-\s+/.test(line)) {
          flush();
          const items = [];
          while (k < lines.length && /^-\s+/.test(lines[k])) {
            items.push(
              `<li>${renderInline(lines[k].replace(/^-\s+/, ""), footnotes)}</li>`,
            );
            k++;
          }
          out.push(`<ul class="finding-list">${items.join("")}</ul>`);
          continue;
        }
        para.push(line);
        k++;
      }
      flush();
    }
    return out.join("");
  }
  function footnotesListEl(footnotes) {
    if (!footnotes.length) return null;
    return el(
      "ol",
      { class: "fn-list" },
      footnotes.map((u, i) =>
        el("li", { id: `fn-${i + 1}` }, [
          el("a", { href: u, target: "_blank", rel: "noopener", text: u }),
        ]),
      ),
    );
  }

  // ---------- data-bind ------------------------------------------------------

  function bind() {
    for (const node of $$("[data-bind]")) {
      const v = path(R, node.getAttribute("data-bind"));
      if (v == null) continue;
      // Ledes may carry [[key]] cross-refs (and inline markup); resolve those to
      // live links. Plain values stay textContent.
      if (typeof v === "string" && v.includes("[["))
        node.innerHTML = renderInline(v, []);
      else node.textContent = v;
    }
    // Hide cover meta pairs whose <dd> ended up empty (e.g. unfilled client).
    for (const pair of $$(".cover-meta .meta-pair")) {
      const dd = pair.querySelector("dd");
      pair.classList.toggle("is-empty", !(dd && dd.textContent.trim()));
    }
  }

  // ---------- severity / heat utilities --------------------------------------

  const SEV_ORDER = ["Critical", "High", "Medium", "Low"];

  function severityFromCvss(score) {
    if (score >= 9.0) return "Critical";
    if (score >= 7.0) return "High";
    if (score >= 4.0) return "Medium";
    return "Low";
  }

  /* ---------- Risk scoring ----------
     Each finding carries `likelihoodInputs` and `impactInputs` (see data.js
     for the scoring rubric). Aggregate scores are computed here so the
     mapping logic lives in one place. */

  function likelihoodScoreOf(f) {
    const i = f.likelihoodInputs || {};
    return (
      0.5 * (i.exposure ?? 50) +
      0.3 * (i.precondition ?? 50) +
      0.2 * (i.discoverability ?? 50)
    );
  }
  function impactScoreOf(f) {
    const i = f.impactInputs || {};
    const vals = [i.scope, i.sensitivity, i.recoverability].filter((v) => v != null);
    if (!vals.length) return 50;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  }

  // Bucket thresholds at 1/3 and 2/3 (33.33 / 66.67).
  const BUCKET_LOW = 100 / 3;
  const BUCKET_HIGH = 200 / 3;
  function bucketOf(score) {
    if (score >= BUCKET_HIGH) return "High";
    if (score >= BUCKET_LOW) return "Moderate";
    return "Low";
  }
  function zoneOf(impactScore, likelihoodScore) {
    const m = { High: 2, Moderate: 1, Low: 0 };
    const s = m[bucketOf(impactScore)] + m[bucketOf(likelihoodScore)];
    if (s >= 3) return "high";
    if (s === 2) return "moderate";
    return "low";
  }

  // ---------- Executive Summary ---------------------------------------------

  function renderSummary() {
    const counts = SEV_ORDER.reduce((acc, s) => ((acc[s] = 0), acc), {});
    for (const f of R.findings || []) {
      const severity = normalizeFindingSeverity(f.severity);
      counts[severity] = (counts[severity] || 0) + 1;
    }

    const chipsRoot = $("#severityChips");
    chipsRoot.innerHTML = "";
    for (const sev of SEV_ORDER) {
      const chip = el(
        "button",
        {
          class: "chip",
          "data-sev": sev,
          "aria-label": `${sev} findings: ${counts[sev]}. Jump to findings.`,
          type: "button",
          onclick: jumpToFindings,
        },
        [
          el("span", { class: "chip-label" }, [el("span", { class: "sev-dot" }), sev]),
          el("span", { class: "chip-count", text: String(counts[sev]) }),
        ],
      );
      chipsRoot.appendChild(chip);
    }

    const ul = $("#takeaways");
    ul.innerHTML = "";
    for (const t of R.takeaways || [])
      ul.appendChild(el("li", { html: renderInline(t, []) }));
  }

  function jumpToFindings() {
    const target = $("#findings");
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---------- Scope ---------------------------------------------------------

  function renderScope() {
    const scope = R.scope || {};
    const fill = (selector, items) => {
      const ul = $(selector);
      if (!ul) return;
      ul.innerHTML = "";
      for (const i of items || []) ul.appendChild(el("li", { text: i }));
    };
    fill("#scopeIn", scope.inScope);
    fill("#scopeOut", scope.outOfScope);
    $("#scopeNotes").textContent = (scope.notes || []).join(" ");
  }

  // ---------- Trust Boundary, Data Flow & Attack Paths ----------------------

  // Mermaid renders asynchronously into a single shared node, so both the
  // in-flight render and the theme it is rendering at are module state.
  let _trustRender = Promise.resolve();
  let _trustTheme = null;

  function renderTrustBoundary() {
    const tb = R.trustBoundary;
    if (!tb) return Promise.resolve();
    const lede = $("#trustSummary");
    if (lede) lede.innerHTML = renderProse(tb.summary || "", []);
    const dia = $("#trustDiagram");
    const pts = $("#trustPoints");
    if (pts) {
      pts.innerHTML = "";
      for (const p of tb.points || []) {
        // Footnotes (lines starting with * / **) render as plain marked lines,
        // not bullets, so they read as diagram footnotes.
        const foot = /^\*{1,2}\s/.test(p);
        pts.appendChild(
          el("li", {
            class: foot ? "trust-footnote" : "",
            html: renderInline(p, []),
          }),
        );
      }
    }
    const ev = $("#trustEvidence");
    if (ev) {
      ev.innerHTML = "";
      for (const e of tb.evidence || [])
        ev.appendChild(el("li", { html: renderInline(e, []) }));
    }
    const showDiagramError = (errMsg) => {
      if (!dia) return;
      dia.className = "diagram-error";
      dia.textContent = errMsg || "Diagram could not be rendered.";
    };
    if (window.mermaid && dia && tb.mermaid) {
      const targetTheme = isDarkMode() ? "dark" : "default";
      // mermaid.run is async: if a print snapshot is taken before it resolves,
      // the diagram prints BLANK. So when the diagram is already rendered (or
      // queued to render) at the theme we need — printing forces light and the
      // screen was already light — keep it instead of wiping + re-rendering.
      // Tracked in a variable, not on the node: the queued render has not
      // touched the DOM yet, so reading the node would compare against the
      // PREVIOUS theme and skip a re-render that is genuinely needed.
      if (_trustTheme === targetTheme && dia.querySelector("svg")) {
        return _trustRender;
      }
      _trustTheme = targetTheme;
      // Serialize renders. Two toggles in quick succession used to run mermaid
      // twice over the same node concurrently: the second call cleared
      // data-processed before the first re-set it, so the second run skipped
      // the node and left the diagram at the wrong theme — and the losing run
      // rejected with nothing attached to catch it.
      _trustRender = _trustRender
        .catch(() => {})
        .then(() => {
          // Re-init + reset the node each call so a theme toggle re-renders the
          // diagram legibly: dark mermaid theme on dark mode, default on light.
          window.mermaid.initialize({
            startOnLoad: false,
            securityLevel: "loose",
            theme: targetTheme,
          });
          dia.className = "mermaid";
          dia.removeAttribute("data-processed");
          // Resolve [[key]] cross-refs to their live display ids (plain text —
          // the diagram can't hold links) before mermaid parses the source.
          dia.textContent = tb.mermaid.replace(/\[\[([a-z0-9]{4,8})\]\]/g, (m, k) =>
            didForKey(k),
          );
          dia.setAttribute("data-mermaid-theme", targetTheme);
          return window.mermaid.run({ nodes: [dia] });
        })
        .catch((e) => {
          // mermaid reports a syntax error by REJECTING, so a synchronous
          // try/catch never saw it — the report showed a blank figure and an
          // unhandled rejection instead of naming the broken diagram.
          console.warn("mermaid render failed", e, "Diagram source:", tb.mermaid);
          showDiagramError(`Diagram syntax error: ${(e && e.message) || e}`);
          _trustTheme = null; // let the next attempt retry rather than no-op
        });
      // Returned so callers (printReport) can await the async render before
      // taking the print snapshot.
      return _trustRender;
    } else if (dia && tb.mermaid) {
      showDiagramError("Mermaid library not loaded");
    }
    return Promise.resolve();
  }

  function renderAttackPaths() {
    const ap = R.attackPaths;
    if (!ap) return;
    const lede = $("#attackSummary");
    if (lede) lede.innerHTML = renderProse(ap.summary || "", []);
    const noteEl = $("#attackNote");
    if (noteEl) noteEl.innerHTML = ap.note ? renderInline(ap.note, []) : "";
    const root = $("#attackList");
    if (!root) return;
    root.innerHTML = "";
    for (const p of ap.paths || []) {
      const chainKids = [
        el("span", { class: "attack-chain-label", text: "Finding chain: " }),
      ];
      (p.chain || []).forEach((fkey, i) => {
        if (i) chainKids.push(document.createTextNode(" → "));
        const fdid = didForKey(fkey);
        chainKids.push(
          el("a", {
            class: "linkchip",
            href: `#finding-${fdid}`,
            text: fdid,
            title: refTitle(fkey),
            onclick: (ev) => {
              ev.preventDefault();
              jumpToFinding(fdid);
            },
          }),
        );
      });
      root.appendChild(
        el("article", { class: "attack-card", id: `attack-${p._did}` }, [
          el("header", { class: "attack-head" }, [
            el("span", { class: "attack-id", text: p._did }),
            el("span", { class: "attack-name", text: p.name }),
          ]),
          el("p", {
            class: "attack-attacker",
            html: "<strong>Attacker:</strong> " + renderInline(p.attacker || "", []),
          }),
          el("div", { class: "attack-chain" }, chainKids),
          el(
            "ol",
            { class: "attack-steps" },
            (p.steps || []).map((s) => el("li", { html: renderInline(s, []) })),
          ),
          el("p", {
            class: "attack-result",
            html: "<strong>Result:</strong> " + renderInline(p.result || "", []),
          }),
          el("details", { class: "attack-evidence" }, [
            el("summary", { text: "Evidence" }),
            el(
              "ul",
              {},
              (p.evidence || []).map((e) => el("li", { html: renderInline(e, []) })),
            ),
          ]),
        ]),
      );
    }
  }

  // ---------- SAMM ----------------------------------------------------------

  function renderSamm() {
    const chart = $("#sammChart");
    if (!chart || !R.samm) return;
    chart.innerHTML = "";

    for (const d of R.samm.domains) {
      const assessed = typeof d.score === "number";
      const heightPct = assessed ? Math.max(2, (d.score / 3) * 100) : 0;
      const valueText = assessed ? d.score.toFixed(2) : "—";
      const wrap = el("div", { class: "samm-bar-wrap" }, [
        el(
          "div",
          {
            class: "samm-bar" + (assessed ? "" : " samm-bar-unassessed"),
            style: `height: ${heightPct}%`,
            title: `${d.name}: ${valueText}`,
          },
          [
            el("span", { class: "samm-bar-value", text: valueText }),
            el("span", { class: "samm-bar-label", text: d.name }),
            d.summary ? el("span", { class: "samm-bar-tip", text: d.summary }) : null,
          ].filter(Boolean),
        ),
      ]);
      chart.appendChild(wrap);
    }
    chart.addEventListener("mouseover", () => chart.classList.add("is-hovering"));
    chart.addEventListener("mouseleave", () => chart.classList.remove("is-hovering"));

    const legend = $("#sammLegend");
    if (!legend) return;
    legend.innerHTML = "";
    for (const b of R.samm.bands) {
      legend.appendChild(
        el("span", {}, [
          el("span", { class: "swatch", style: `background:${b.color}` }),
          `${b.name} (${b.min.toFixed(1)}–${b.max.toFixed(1)})`,
        ]),
      );
    }
  }

  // ---------- Strengths -----------------------------------------------------

  function renderStrengths() {
    const ul = $("#strengthsList");
    ul.innerHTML = "";
    for (const s of STRENGTHS_ORDERED) {
      ul.appendChild(
        el("li", { id: `strength-${s._did}` }, [
          el("span", { class: "s-id", text: s._did }),
          el("span", { class: "s-title", text: s.title }),
          el("div", { class: "s-detail", html: renderInline(s.detail, []) }),
        ]),
      );
    }
  }

  // ---------- Heat Map ------------------------------------------------------

  /* Risk matrix axes are continuous 0–100 (computed from scoring inputs).
     Axis labels at 16.67 / 50 / 83.33 show the Low / Moderate / High band
     names so the reader doesn't need to translate numeric scores. */
  const BAND_LABEL_X = { 16.67: "Low", 50: "Moderate", 83.33: "High" };
  const BAND_LABEL_Y = { 16.67: "Low", 50: "Moderate", 83.33: "High" };

  const SEV_COLOR = {
    Critical: "#B12B2B",
    High: "#D9531E",
    Medium: "#C28F12",
    Low: "#1F6FBF",
  };
  const ZONE_COLOR = {
    low: "rgba(0,127,127,0.10)",
    moderate: "rgba(217,131,30,0.16)",
    high: "rgba(177,43,43,0.18)",
  };

  /* Resolve the current Zenable palette from CSS variables so charts adapt
     to light/dark mode the same way the rest of the page does. */
  function chartTheme() {
    if (document.body.classList.contains("print-light-render")) {
      return {
        ink: "#0A2540",
        inkMute: "#4A5A6E",
        mute: "#7B8794",
        rule: "#E4E9EF",
        ruleSoft: "#EFF2F6",
        paper: "#FFFFFF",
        teal: "#007F7F",
        tealDark: "#006666",
        blue: "#05385B",
        blueLight: "#064A77",
      };
    }
    const cs = getComputedStyle(document.documentElement);
    const v = (n, fallback) => cs.getPropertyValue(n).trim() || fallback;
    return {
      ink: v("--z-ink", "#0A2540"),
      inkMute: v("--z-ink-mute", "#4A5A6E"),
      mute: v("--z-mute", "#7B8794"),
      rule: v("--z-rule", "#E4E9EF"),
      ruleSoft: v("--z-rule-soft", "#EFF2F6"),
      paper: v("--z-paper", "#FFFFFF"),
      teal: v("--z-teal", "#007F7F"),
      tealDark: v("--z-teal-dark", "#006666"),
      blue: v("--z-blue", "#05385B"),
      blueLight: v("--z-blue-light", "#064A77"),
    };
  }

  /* Every chart is disposed and re-created whenever the theme or the print
     palette changes (echarts bakes colors in at setOption time). A resize
     listener that closed over the chart instance it was registered with would
     therefore be driving a DISPOSED chart after the first toggle, throwing on
     each resize and leaving the layout stale. Attach once per container and
     always resize whatever `node._chart` currently holds.
     On print, resize to the CONTAINER (not a fixed box): once print media is
     active the container is at the true print width, so echarts fills the page
     exactly — a hardcoded box only ever filled a fraction of it. */
  function attachChartResize(node) {
    if (!node || node._resizeAttached) return;
    const safeResize = () => {
      const c = node._chart;
      if (c && !(c.isDisposed && c.isDisposed())) c.resize();
    };
    window.addEventListener("resize", safeResize);
    window.addEventListener("beforeprint", safeResize);
    window.addEventListener("afterprint", safeResize);
    // Safari/Chromium emit matchMedia change in addition to beforeprint; it
    // fires once print media (and its layout) is active, so the container is at
    // the print width here — resizing to it fills the page.
    const mq = window.matchMedia && window.matchMedia("print");
    if (mq && mq.addEventListener) mq.addEventListener("change", safeResize);
    node._resizeAttached = true;
  }

  function renderHeatmap() {
    const container = $("#heatmapChart");
    if (!container || !window.echarts) return;

    // ----- 1. Risk-zone background rectangles -----
    // 9 cells from band boundaries [0, 33.33, 66.67, 100].
    const bounds = [0, BUCKET_LOW, BUCKET_HIGH, 100];
    const zoneRects = [];
    for (let yi = 0; yi < 3; yi++) {
      // impact band
      for (let xi = 0; xi < 3; xi++) {
        // likelihood band
        const zone = zoneOf(
          // midpoints — used only to bucket-back-to-zone-color
          (bounds[yi] + bounds[yi + 1]) / 2,
          (bounds[xi] + bounds[xi + 1]) / 2,
        );
        zoneRects.push([
          {
            xAxis: bounds[xi],
            yAxis: bounds[yi],
            itemStyle: { color: ZONE_COLOR[zone] },
          },
          { xAxis: bounds[xi + 1], yAxis: bounds[yi + 1] },
        ]);
      }
    }

    // ----- 2. Each finding plotted at its exact (likelihood, impact) score -----
    const labelColor = chartTheme().ink;
    const scatterData = R.findings.map((f) => {
      const lScore = likelihoodScoreOf(f);
      const iScore = impactScoreOf(f);
      return {
        value: [lScore, iScore],
        name: f._did,
        itemStyle: {
          color: SEV_COLOR[normalizeFindingSeverity(f.severity)] || "#1F6FBF",
        },
        label: {
          show: true,
          position: "right",
          offset: [5, 0],
          formatter: f._did,
          color: labelColor,
          fontWeight: 700,
          fontSize: 11,
          fontFamily: "JetBrains Mono, SF Mono, Menlo, monospace",
        },
      };
    });

    // De-overlap: findings sharing (near-)identical likelihood/impact scores land
    // on the same dot and their labels stack. Spread each colliding cluster around
    // its shared point on a small deterministic circle so every id stays legible.
    // Bucket on a coarse grid (~4 score units ≈ one label height) so NEAR — not
    // just exactly equal — points cluster, then fan each cluster around its
    // centroid on a circle big enough to clear stacked labels.
    const CELL = 4;
    const clusters = {};
    scatterData.forEach((d) => {
      const k = `${Math.round(d.value[0] / CELL)}|${Math.round(d.value[1] / CELL)}`;
      (clusters[k] = clusters[k] || []).push(d);
    });
    for (const k in clusters) {
      const g = clusters[k];
      if (g.length < 2) continue;
      const cx = g.reduce((s, d) => s + d.value[0], 0) / g.length;
      const cy = g.reduce((s, d) => s + d.value[1], 0) / g.length;
      const radius = 3 + g.length; // grows with cluster size
      g.forEach((d, i) => {
        const ang = (2 * Math.PI * i) / g.length + Math.PI / 6;
        d.value = [
          Math.max(0, Math.min(100, cx + radius * Math.cos(ang))),
          Math.max(0, Math.min(100, cy + radius * Math.sin(ang))),
        ];
      });
    }

    const findingById = Object.fromEntries(R.findings.map((f) => [f._did, f]));

    // ----- 3. Mount chart -----
    if (container._chart) {
      container._chart.dispose();
    }
    // SVG renderer for print fidelity; echarts sizes to the container (width:100%),
    // and the print resize listeners re-fit it when print media activates.
    const chart = echarts.init(container, null, { renderer: "svg" });
    container._chart = chart;

    const t = chartTheme();

    /* Custom-positioned tick marks and labels:
         - Tick marks AT band boundaries (33.33 and 66.67) act as the
           visible "divider lines" between Low/Moderate/High zones.
         - Labels at the band MIDPOINTS (16.67 / 50 / 83.33) so each
           band-label sits centered under its zone. */
    const axisCommon = {
      type: "value",
      min: 0,
      max: 100,
      axisLine: { lineStyle: { color: t.rule } },
      axisTick: {
        show: true,
        customValues: [BUCKET_LOW, BUCKET_HIGH],
        lineStyle: { color: t.ink },
        length: 6,
      },
      splitLine: {
        show: true,
        customValues: [BUCKET_LOW, BUCKET_HIGH],
        lineStyle: { color: t.paper, width: 2 },
      },
      axisLabel: {
        customValues: [100 / 6, 50, 500 / 6], // 16.67 / 50 / 83.33
        color: t.ink,
        fontSize: 11,
        fontFamily: "Raleway, sans-serif",
        fontWeight: 600,
        formatter: () => "",
      },
    };

    chart.setOption({
      animation: false,
      grid: { left: 80, right: 32, top: 22, bottom: 60, containLabel: false },
      tooltip: {
        trigger: "item",
        confine: true,
        backgroundColor: "#0A2540",
        borderWidth: 0,
        textStyle: { color: "#fff", fontSize: 11, fontFamily: "Raleway, sans-serif" },
        padding: [8, 10],
        extraCssText: "max-width: 320px; white-space: normal;",
        formatter: (p) => {
          if (p.seriesName !== "Findings") return "";
          const f = findingById[p.name];
          if (!f) return p.name;
          const severity = normalizeFindingSeverity(f.severity);
          const dot =
            `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;` +
            `background:${SEV_COLOR[severity] || "#1F6FBF"};margin:0 5px;vertical-align:middle;"></span>`;
          const impact = bucketOf(impactScoreOf(f));
          const likelihood = bucketOf(likelihoodScoreOf(f));
          return (
            `<b>${f._did}</b>${dot}${severity}` +
            `<br/>Impact: ${impact}<br/>Likelihood: ${likelihood}` +
            `<br/><br/>${escapeHtml(f.title)}`
          );
        },
      },
      xAxis: {
        ...axisCommon,
        name: "Likelihood",
        nameLocation: "middle",
        nameGap: 36,
        nameTextStyle: {
          color: t.ink,
          fontWeight: 700,
          fontSize: 11,
          fontFamily: "Raleway, sans-serif",
          letterSpacing: 1.4,
        },
        axisLabel: {
          ...axisCommon.axisLabel,
          formatter: (v) => BAND_LABEL_X[+v.toFixed(2)] || "",
        },
      },
      yAxis: {
        ...axisCommon,
        name: "Impact",
        nameLocation: "middle",
        nameGap: 56,
        nameRotate: 90,
        nameTextStyle: {
          color: t.ink,
          fontWeight: 700,
          fontSize: 11,
          fontFamily: "Raleway, sans-serif",
          letterSpacing: 1.4,
        },
        axisLabel: {
          ...axisCommon.axisLabel,
          formatter: (v) => BAND_LABEL_Y[+v.toFixed(2)] || "",
        },
      },
      series: [
        {
          name: "Findings",
          type: "scatter",
          data: scatterData,
          symbolSize: 16,
          itemStyle: {
            borderColor: t.paper,
            borderWidth: 2,
            shadowBlur: 3,
            shadowColor: "rgba(10,37,64,0.25)",
            shadowOffsetY: 1,
          },
          markArea: {
            silent: true,
            label: { show: false },
            data: zoneRects,
            z: 1,
          },
          emphasis: {
            focus: "self",
            scale: 1.4,
            itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.35)" },
            label: { fontSize: 12 },
          },
          blurScope: "coordinateSystem",
          blur: { itemStyle: { opacity: 0.2 }, label: { opacity: 0.25 } },
          z: 5,
        },
      ],
    });

    chart.on("click", (params) => {
      if (params.seriesName === "Findings" && params.name) {
        jumpToFinding(params.name);
      }
    });

    // Resize handling — keep SVG crisp if the page reflows or print fires.
    attachChartResize(container);

    // ----- 4. Key (legend list) under the chart -----
    const key = $("#heatmapKey");
    key.innerHTML = "";
    for (const f of FINDINGS_ORDERED) {
      key.appendChild(
        el("div", { class: "k-row" }, [
          el("span", { class: "k-id", text: f._did }),
          el("span", { text: f.title }),
        ]),
      );
    }
  }

  // ---------- Findings ------------------------------------------------------

  function renderFindings() {
    const root = $("#findingsList");
    root.innerHTML = "";
    for (const f of FINDINGS_ORDERED) {
      const card = el(
        "article",
        {
          class: "finding",
          id: `finding-${f._did}`,
          dataset: { sev: normalizeFindingSeverity(f.severity), id: f._did },
        },
        [
          el(
            "header",
            {
              class: "finding-head",
              // Only the header bar (id + title + severity) toggles the card, so
              // the body stays selectable for copy/paste and its links/downloads
              // are clickable without collapsing the finding.
              onclick: () => card.classList.toggle("is-open"),
            },
            [
              el("span", { class: "finding-id", text: f._did }),
              el("span", { class: "finding-title", text: f.title }),
              el("span", {
                class: "finding-badge",
                "data-sev": normalizeFindingSeverity(f.severity),
                text: normalizeFindingSeverity(f.severity),
              }),
            ],
          ),
          (function () {
            const footnotes = [];
            const proseHtml = renderProse(f.detail || "", footnotes);
            const evidenceItems = (f.evidence || []).map((e) =>
              el("li", { html: renderInline(e, footnotes) }),
            );
            const refsEl = footnotesListEl(footnotes);
            return el("div", { class: "finding-body" }, [
              el("div", { class: "finding-prose", html: proseHtml }),
              evidenceItems.length
                ? el("details", { class: "finding-collapse finding-evidence" }, [
                    el("summary", { text: "Evidence" }),
                    el("ul", { class: "evidence-list" }, evidenceItems),
                  ])
                : null,
              refsEl
                ? el("details", { class: "finding-collapse" }, [
                    el("summary", { text: "References" }),
                    refsEl,
                  ])
                : null,
              el("h4", { text: "Linked" }),
              el(
                "div",
                { class: "finding-links" },
                [
                  f.recommendationKey
                    ? el("a", {
                        class: "linkchip",
                        href: `#rec-${didForKey(f.recommendationKey)}`,
                        onclick: linkChipNav,
                        text: `Recommendation ${didForKey(f.recommendationKey)}`,
                      })
                    : null,
                  ...(f.relatedCveIds || []).map((cid) =>
                    el("a", {
                      class: "linkchip",
                      href: `#cve-${cid}`,
                      onclick: linkChipNav,
                      text: cid,
                    }),
                  ),
                ].filter(Boolean),
              ),
            ]);
          })(),
        ],
      );
      root.appendChild(card);
    }

    root.addEventListener("mouseover", () => root.classList.add("is-hovering"));
    root.addEventListener("mouseleave", () => root.classList.remove("is-hovering"));
  }

  function jumpToFinding(id) {
    const target = $(`#finding-${id}`);
    if (!target) return;
    // clear prior targets
    $$(".finding.is-target").forEach((n) => n.classList.remove("is-target"));
    target.classList.add("is-target", "is-open");
    target.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // ---------- CVEs ----------------------------------------------------------

  function renderCves() {
    const root = $("#cvesList");
    if (!root) return;
    root.innerHTML = "";
    const lede = $("#cves .section-lede");
    const cves = R.cves || [];
    // Empty state: a clear "nothing here" line instead of the descriptive intro.
    if (!cves.length) {
      if (lede) lede.textContent = "No confirmed exploitable CVEs.";
      return;
    }
    if (lede)
      lede.textContent = "CVEs with a confirmed exploitable pathway through this code.";
    // Otherwise: an auto-built table from the cve data (same look as appendix tables).
    const cols = [
      "CVE",
      "Package",
      "CVSS",
      "Affected range",
      "Fixed in",
      "Exploitable pathway",
      "Linked finding",
    ];
    const headRow = el(
      "tr",
      {},
      cols.map((h) => el("th", { text: h })),
    );
    const bodyRows = cves.map((c) => {
      // A CVE with no CVSS block used to throw here and take the WHOLE table
      // down with it (safeRender swallows the error, so §8 just rendered empty).
      const cvss = c.cvss || {};
      const score = typeof cvss.score === "number" ? cvss.score : null;
      const sev = cvss.severity || (score != null ? severityFromCvss(score) : "");
      const fkey = c.relatedFindingKey || c.relatedFindingId;
      const fdid = fkey ? didForKey(fkey) : "";
      return el("tr", { id: `cve-${c.id}` }, [
        el(
          "td",
          {},
          el("a", {
            class: "finding-ref",
            href: c.reference,
            target: "_blank",
            rel: "noopener",
            text: c.id,
          }),
        ),
        el("td", { text: c.package }),
        el(
          "td",
          {},
          score != null
            ? el("span", {
                class: "cvss-score",
                "data-sev": sev,
                text: `${score.toFixed(1)} ${sev}`.trim(),
              })
            : el("span", { text: sev || "—" }),
        ),
        el("td", { text: c.affectedRange || "—" }),
        el("td", { text: c.fixedIn || "—" }),
        el("td", { text: c.exploitablePathway }),
        el(
          "td",
          {},
          fdid
            ? el("a", {
                class: "finding-ref",
                href: `#finding-${fdid}`,
                text: fdid,
              })
            : el("span", { text: "—" }),
        ),
      ]);
    });
    root.appendChild(
      el("table", { class: "artifacts-table cve-table" }, [
        el("thead", {}, headRow),
        el("tbody", {}, bodyRows),
      ]),
    );
  }

  // ---------- Custom Requirements --------------------------------------------------

  function renderCustomRequirements() {
    const root = $("#customRequirementsList");
    if (!root || !R.customRequirements) return;
    root.innerHTML = "";
    for (const s of R.customRequirements.sections || []) {
      // Authored prose here goes through the same markdown pipeline as every
      // other prose field (findings, strengths, attack paths). Rendering it as
      // textContent left `code`, **bold**, [[key]] cross-refs and links showing
      // as raw source. Footnotes are collected in reading order.
      const footnotes = [];
      const questionHtml = s.question ? renderInline(s.question, footnotes) : "";
      const findingHtml = renderProse(s.finding || "", footnotes);
      const evidenceItems = (s.evidence || []).map((e) =>
        el("li", { html: renderInline(e, footnotes) }),
      );
      const refsEl = footnotesListEl(footnotes);
      const status = String(s.status || "");
      root.appendChild(
        el(
          "article",
          { class: "tok-card" },
          [
            el("header", { class: "tok-head" }, [
              el("span", { class: "tok-title", text: s.title }),
              status
                ? el("span", {
                    class: "tok-status",
                    "data-status": status,
                    text: status.replace(/-/g, " "),
                  })
                : null,
            ].filter(Boolean)),
            questionHtml ? el("div", { class: "tok-q", html: questionHtml }) : null,
            el("div", { class: "tok-body finding-prose", html: findingHtml }),
            evidenceItems.length
              ? el("ul", { class: "tok-evidence" }, evidenceItems)
              : null,
            refsEl
              ? el("details", { class: "finding-collapse" }, [
                  el("summary", { text: "References" }),
                  refsEl,
                ])
              : null,
          ].filter(Boolean),
        ),
      );
    }
  }

  // ---------- Recommendations -----------------------------------------------

  function renderRecs() {
    const root = $("#recsList");
    root.innerHTML = "";
    for (const r of RECS_ORDERED) {
      const relDids = (r.relatedFindingKeys || []).map(didForKey);
      root.appendChild(
        el(
          "article",
          {
            class: "rec",
            id: `rec-${r._did}`,
            onmouseenter: () => {
              for (const fdid of relDids) {
                const fn = $(`#finding-${fdid}`);
                if (fn) fn.classList.add("is-target");
              }
            },
            onmouseleave: () => {
              for (const fdid of relDids) {
                const fn = $(`#finding-${fdid}`);
                if (fn) fn.classList.remove("is-target");
              }
            },
          },
          [
            el("span", { class: "rec-id", text: r._did }),
            el("span", { class: "rec-title", text: r.title }),
            el("span", {
              class: "rec-priority",
              "data-priority": r.priority,
              text: r.priority,
            }),
            el(
              "span",
              { class: "rec-links" },
              (r.relatedFindingKeys || []).map((fkey) => {
                const fdid = didForKey(fkey);
                return el("a", {
                  class: "linkchip",
                  href: `#finding-${fdid}`,
                  // Title shows "F-NNN: <finding title>" on hover, matching the
                  // prose [[key]] cross-refs and the finding cards' own chips.
                  title: refTitle(fkey),
                  text: fdid,
                  onclick: (ev) => {
                    ev.stopPropagation();
                    jumpToFinding(fdid);
                    ev.preventDefault();
                  },
                });
              }),
            ),
            el("div", { class: "rec-detail", html: renderInline(r.detail, []) }),
          ],
        ),
      );
    }
    root.addEventListener("mouseover", () => root.classList.add("is-hovering"));
    root.addEventListener("mouseleave", () => root.classList.remove("is-hovering"));
  }

  // ---------- Investigator --------------------------------------------------

  function renderInvestigator() {
    $("#investigatorStatement").innerHTML = renderInline(R.investigator.statement, []);
    const contribs = R.investigator.contributors || [];
    $("#investigatorContributors").textContent = contribs.length
      ? contribs.join(", ")
      : "—";
  }

  // ---------- Appendices ----------------------------------------------------

  function renderAppendices() {
    const art = loadInlineJson("artifacts-data");
    const note = art?.note;
    const items = art?.items;
    $("#appendixANote").textContent = note || "";
    const tbody = $("#artifactsBody");
    tbody.innerHTML = "";
    for (const a of items || []) {
      tbody.appendChild(
        el("tr", {}, [
          el("td", { text: a.name }),
          el("td", { class: "kind", text: a.kind }),
          el(
            "td",
            { class: "hash" },
            [
              el("code", { text: a.sha256 }),
              // Generated hashes flag whether they reproduce from the pinned commit;
              // an out-of-band artifact (reproducible:false) gets a visible caveat.
              a.reproducible === false
                ? el("span", {
                    class: "hash-caveat",
                    text: " (not reproducible from commit)",
                  })
                : null,
            ].filter(Boolean),
          ),
        ]),
      );
    }

    const u = $("#unconfirmedList");
    u.innerHTML = "";
    for (const item of R.unconfirmed || []) {
      // `detail` and `followUp` are authored markdown like every other prose
      // field. `followUp` used to be appended as a raw string node, so its
      // backticks, links and [[key]] cross-refs printed as literal source.
      const footnotes = [];
      const detailHtml = renderInline(item.detail || "", footnotes);
      const followHtml = item.followUp ? renderInline(item.followUp, footnotes) : "";
      const refsEl = footnotesListEl(footnotes);
      u.appendChild(
        el(
          "li",
          {},
          [
            el("span", { class: "u-id", text: item.id }),
            el("span", { class: "u-title", text: item.title }),
            el("div", { class: "u-detail", html: detailHtml }),
            followHtml
              ? el("div", {
                  class: "u-follow",
                  html: "<b>Follow-up: </b>" + followHtml,
                })
              : null,
            refsEl
              ? el("details", { class: "finding-collapse" }, [
                  el("summary", { text: "References" }),
                  refsEl,
                ])
              : null,
          ].filter(Boolean),
        ),
      );
    }
  }

  // ---------- Appendix D — License & Dependency Inventory ------------------

  function renderDependencies() {
    const D = loadInlineJson("dependencies-data");
    if (!D) return;
    $("#appendixDNote").textContent = D.note || "";

    // Order mirrors the section order in index.html: vulnerabilities (D.1)
    // first, then the provenance and inventory that back them.
    const vulns = D.vulnerabilities || [];
    const vulnsEmpty = $("#depVulnsEmpty");
    if (vulnsEmpty) {
      vulnsEmpty.textContent = vulns.length ? "" : "No known vulnerabilities found.";
    }
    const vulnBody = $("#depVulnsBody");
    vulnBody.innerHTML = "";
    for (const v of vulns) {
      vulnBody.appendChild(
        el("tr", {}, [
          el("td", {}, el("code", { text: v.id })),
          el(
            "td",
            {},
            el("span", {
              class: "finding-badge",
              "data-sev": v.severity,
              text: v.severity,
            }),
          ),
          el("td", {}, el("code", { text: v.package })),
          el("td", { class: "kind", text: v.version }),
          el("td", { text: v.fixed_in || "—" }),
        ]),
      );
    }

    const scansBody = $("#depScansBody");
    scansBody.innerHTML = "";
    for (const s of D.scans || []) {
      scansBody.appendChild(
        el("tr", {}, [
          el("td", { text: s.tool }),
          el("td", { class: "kind", text: s.version }),
          el("td", { text: s.target }),
          el("td", {}, el("code", { text: s.output })),
          el("td", { text: s.result }),
        ]),
      );
    }

    const compBody = $("#depComponentsBody");
    compBody.innerHTML = "";
    for (const c of D.components || []) {
      const licenses = c.verified_licenses || c.licenses || [];
      const licenseSource = c.license_source ? `Source: ${c.license_source}` : "";
      compBody.appendChild(
        el("tr", {}, [
          el("td", {}, el("code", { text: c.name })),
          el("td", { class: "kind", text: c.version }),
          el("td", { text: c.type }),
          el("td", { text: licenses.join(", ") || "—", title: licenseSource }),
          el("td", { text: (c.targets || []).join(", ") }),
        ]),
      );
    }

    const licBody = $("#depLicensesBody");
    licBody.innerHTML = "";
    for (const lc of D.licenses || []) {
      licBody.appendChild(
        el("tr", {}, [
          el("td", { text: lc.license }),
          el("td", { text: String(lc.count) }),
        ]),
      );
    }
  }

  // ---------- Optional generated extension appendices -----------------------

  function appendExtensionTocEntry(app) {
    const toc = $("#appendixTocList");
    if (!toc || !app.id || !app.label || !app.title) return;
    if ($(`a[href="#${app.id}"]`, toc)) return;
    toc.appendChild(
      el(
        "li",
        {},
        el("a", { href: `#${app.id}` }, [
          el("span", { class: "toc-num", text: app.label }),
          el("span", { class: "toc-text", text: app.title }),
        ]),
      ),
    );
  }

  function renderExtensionGroup(group) {
    const children = [
      el("h3", { text: `${group.id || ""} — ${group.title || ""}`.trim() }),
    ];
    const relKey = group.relatedFindingKey || group.relatedFindingId;
    if (relKey) {
      const relDid = didForKey(relKey);
      children.push(
        el("p", { class: "section-lede" }, [
          "Related finding: ",
          el("a", {
            class: "finding-ref",
            href: `#finding-${relDid}`,
            title: refTitle(relKey),
            text: relDid,
          }),
        ]),
      );
    }
    if (group.lede) {
      children.push(el("p", { html: renderInline(group.lede, []) }));
    }
    if ((group.provenance || []).length) {
      children.push(
        el(
          "ul",
          { class: "evidence-list" },
          group.provenance.map((p) => el("li", { html: renderInline(p, []) })),
        ),
      );
    }
    if ((group.items || []).length) {
      children.push(
        el("table", { class: "artifacts-table extension-table" }, [
          el(
            "thead",
            {},
            el("tr", {}, [
              el("th", { text: "Symbol" }),
              el("th", { text: "Location" }),
              el("th", { text: "Note" }),
            ]),
          ),
          el(
            "tbody",
            {},
            group.items.map((item) =>
              el("tr", {}, [
                el("td", { text: item.symbol || "" }),
                el("td", {}, el("code", { text: item.location || "" })),
                el("td", { html: renderInline(item.note || "", []) }),
              ]),
            ),
          ),
        ]),
      );
    }
    return el("section", { class: "extension-group" }, children);
  }

  function renderExtensionAppendices() {
    const data = loadInlineJson("extensions-data");
    const root = $("#extensionAppendices");
    if (!data || !root) return;
    root.innerHTML = "";
    for (const app of data.appendices || []) {
      if (!app.id || !app.label || !app.title) continue;
      appendExtensionTocEntry(app);
      root.appendChild(
        el("section", { id: app.id, class: "page extension-appendix" }, [
          el(
            "header",
            { class: "section-head" },
            [
              el("h2", { text: `Appendix ${app.label} — ${app.title}` }),
              app.note
                ? el("p", { class: "section-lede", html: renderInline(app.note, []) })
                : null,
            ].filter(Boolean),
          ),
          ...(app.groups || []).map(renderExtensionGroup),
        ]),
      );
    }
  }

  // ---------- Appendix C — Repository History --------------------------------

  const RACE_PALETTE = [
    "#007F7F",
    "#05385B",
    "#00BAAE",
    "#D9531E",
    "#1F6FBF",
    "#C28F12",
    "#7F4FBF",
    "#B12B2B",
    "#2A8F6F",
    "#064A77",
    "#7B8794",
    "#3FA9A5",
    "#8C3E13",
    "#5F2E80",
    "#0E5C9E",
    "#9C7A0B",
    "#2D7A35",
    "#A82A66",
    "#0E6D6D",
    "#4A3F12",
  ];

  function fmtHours(h) {
    if (h == null) return "—";
    if (h < 1) return (h * 60).toFixed(0) + "m";
    if (h < 48) return h.toFixed(1) + "h";
    return (h / 24).toFixed(1) + "d";
  }

  function metricCard(label, value, hint) {
    return el(
      "div",
      { class: "metric-card" },
      [
        el("div", { class: "metric-label", text: label }),
        el("div", { class: "metric-value", text: String(value) }),
        hint ? el("div", { class: "metric-hint", text: hint }) : null,
      ].filter(Boolean),
    );
  }

  // Read a `<script type="application/json">` evidence block by id, stripping the
  // `<!-- TAG-BEGIN/END -->` markers its transform script writes between. Returns
  // null when the block is absent, empty, or literal `null` (not yet generated).
  function loadInlineJson(id) {
    const node = document.getElementById(id);
    if (!node) return null;
    try {
      const raw = node.textContent
        .replace(/<!--\s*[A-Z]+-(BEGIN|END)\s*-->/g, "")
        .trim();
      if (!raw || raw === "null") return null;
      return JSON.parse(raw);
    } catch (e) {
      console.error(id + " parse failed", e);
      return null;
    }
  }

  function loadMetricsData() {
    return loadInlineJson("metrics-data");
  }

  function renderRepoMetrics() {
    const data = loadMetricsData();
    if (!data) return;

    // Lede with generated timestamp
    const lede = $("#repoMetricsLede");
    if (lede && data.summary) {
      const dateRange = [data.summary.first_commit, data.summary.last_commit]
        .filter(Boolean)
        .join(" → ");
      const generated = data.generated_at ? `Generated ${data.generated_at} · ` : "";
      lede.innerHTML =
        `Derived from <code>git log</code> on the provided working copy. ` +
        `<span style="color:var(--z-ink);">${generated}${dateRange}</span>`;
    }

    // ----- Summary cards -----
    const s = data.summary || {};
    const sc = $("#repoSummaryCards");
    sc.innerHTML = "";
    sc.append(
      metricCard("Total commits", Number(s.total_commits).toLocaleString()),
      metricCard("Unique authors", s.unique_authors),
      metricCard("Merge commits", Number(s.total_merge_commits).toLocaleString()),
      metricCard(
        "PR merges",
        Number(s.total_pr_merges).toLocaleString(),
        s.pr_merges_pct_of_commits + "% of commits",
      ),
      metricCard(
        "Revert commits",
        s.revert_commits,
        "Proxy for change-failure rate: " + s.change_failure_rate_pct + "%",
      ),
      metricCard("Fix/hotfix commits", s.fix_commits),
    );

    // ----- PR cards -----
    // Squash-merge / rebase-only repos legitimately have zero PR merges. Showing
    // a row of "0.0h / 0% / 0%" cards would mislead the reader into thinking the
    // team has no PR workflow — hide the whole subsection instead.
    const p = data.pr_stats || {};
    const prSection = $("#repoPrSection");
    if (!s.uses_pr_workflow || !p.total_pr_merges) {
      if (prSection) prSection.style.display = "none";
    } else {
      const pc = $("#repoPrCards");
      pc.innerHTML = "";
      pc.append(
        metricCard(
          "Median PR open",
          fmtHours(p.median_hours),
          "p25: " + fmtHours(p.p25_hours) + " · p75: " + fmtHours(p.p75_hours),
        ),
        metricCard(
          "p90 PR open",
          fmtHours(p.p90_hours),
          "p95: " + fmtHours(p.p95_hours),
        ),
        metricCard(
          "Mean PR open",
          fmtHours(p.mean_hours),
          "Max: " + fmtHours(p.max_hours),
        ),
        metricCard("Closed < 1 day", p.closed_lt_1_day_pct + "%"),
        metricCard("Closed < 1 week", p.closed_lt_1_week_pct + "%"),
        metricCard("Closed < 1 month", p.closed_lt_1_month_pct + "%"),
      );
    }

    // ----- Authors table -----
    if (data.authors) buildAuthorsTable(data.authors);

    if (!window.echarts) {
      markChartsUnavailable();
      return;
    }

    // ----- Yearly chart -----
    if (data.dora) buildYearlyChart(data.dora);

    // ----- Race chart -----
    if (data.racing_chart) buildRaceChart(data.racing_chart);

    // ----- Commit-size-over-time chart -----
    if (data.loc_per_month) buildCommitSizeChart(data.loc_per_month);
  }

  function markChartsUnavailable() {
    for (const node of [$("#yearlyChart"), $("#raceChart"), $("#commitSizeChart")]) {
      if (!node) continue;
      node.classList.add("chart-unavailable");
      node.textContent = "Chart library unavailable.";
    }
    const scrub = $("#raceScrub");
    const nowLabel = $("#raceNowLabel");
    const playBtn = $("#racePlay");
    const resetBtn = $("#raceReset");
    if (scrub) scrub.disabled = true;
    if (playBtn) playBtn.disabled = true;
    if (resetBtn) resetBtn.disabled = true;
    if (nowLabel) nowLabel.textContent = "—";
  }

  // Inverse of markChartsUnavailable, for when a chart library arrives after
  // the bounded boot wait: reset the placeholder nodes and controls so the
  // late re-render starts from the same state as a lib-present boot.
  function clearChartsUnavailable() {
    for (const node of [$("#yearlyChart"), $("#raceChart"), $("#commitSizeChart")]) {
      if (!node) continue;
      node.classList.remove("chart-unavailable");
      node.textContent = "";
    }
    const scrub = $("#raceScrub");
    const playBtn = $("#racePlay");
    const resetBtn = $("#raceReset");
    if (scrub) scrub.disabled = false;
    if (playBtn) playBtn.disabled = false;
    if (resetBtn) resetBtn.disabled = false;
  }

  function buildAuthorsTable(authors) {
    const rows = authors.map((a, i) => ({ ...a, rank: i + 1 }));
    const table = $("#authorsTable");
    if (!table) return;
    const tbody = table.querySelector("tbody");
    const headers = Array.from(table.querySelectorAll("thead th"));
    let sortKey = "rank";
    let sortDir = 1;
    table.classList.add("sortable-table");
    table.dataset.sortBound = "true";

    function paint() {
      const type = headers.find((h) => h.dataset.key === sortKey).dataset.type;
      rows.sort((a, b) => {
        let av = a[sortKey],
          bv = b[sortKey];
        if (sortKey === "emails") {
          av = (av || []).join(",");
          bv = (bv || []).join(",");
        }
        if (type === "num") return (av - bv) * sortDir;
        if (type === "date") return (new Date(av) - new Date(bv)) * sortDir;
        return String(av).localeCompare(String(bv)) * sortDir;
      });
      tbody.innerHTML = "";
      const fmt = (n) => (n == null ? "" : Number(n).toLocaleString());
      // Cells are built with textContent, never innerHTML. Author names, emails,
      // and dates come from the ASSESSED repo's git history — untrusted
      // third-party input by definition — so anyone who can land a commit there
      // could otherwise store script in the report the reviewer opens.
      const cell = (tr, value, className) => {
        const td = document.createElement("td");
        if (className) td.className = className;
        td.textContent = value == null ? "" : String(value);
        tr.appendChild(td);
      };
      for (const a of rows) {
        const tr = document.createElement("tr");
        cell(tr, a.rank, "num");
        cell(tr, a.author);
        cell(tr, fmt(a.commits), "num");
        cell(tr, fmt(a.additions), "num");
        cell(tr, fmt(a.deletions), "num");
        cell(tr, a.first_commit);
        cell(tr, a.last_commit);
        cell(tr, fmt(a.span_days), "num");
        cell(tr, (a.emails || []).join(", "), "emails");
        tbody.appendChild(tr);
      }
      for (const h of headers) {
        const arrow = h.querySelector(".arrow");
        if (h.dataset.key === sortKey) {
          h.classList.add("sorted");
          if (arrow) arrow.textContent = sortDir === 1 ? " ▲" : " ▼";
        } else {
          h.classList.remove("sorted");
          if (arrow) arrow.textContent = "";
        }
      }
    }

    for (const h of headers) {
      const sortByHeader = () => {
        if (sortKey === h.dataset.key) sortDir *= -1;
        else {
          sortKey = h.dataset.key;
          sortDir = h.dataset.type === "str" ? 1 : -1;
          if (sortKey === "rank") sortDir = 1;
        }
        paint();
      };
      h.setAttribute("tabindex", "0");
      h.setAttribute("role", "button");
      h.addEventListener("click", sortByHeader);
      h.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        sortByHeader();
      });
    }
    paint();
  }

  function tableCellText(row, index) {
    return (row.cells[index]?.textContent || "").trim();
  }

  function detectTableColumnType(rows, index) {
    const values = rows
      .map((row) => tableCellText(row, index))
      .filter((value) => value && value !== "—");
    if (!values.length) return "str";
    if (
      values.every((value) =>
        /^-?\d+(?:,\d{3})*(?:\.\d+)?%?$/.test(value.replace(/\s+/g, "")),
      )
    ) {
      return "num";
    }
    if (
      values.every(
        (value) =>
          /^\d{4}-\d{2}-\d{2}(?:[T\s].*)?$/.test(value) &&
          !Number.isNaN(Date.parse(value)),
      )
    ) {
      return "date";
    }
    return "str";
  }

  function comparableTableValue(value, type) {
    if (!value || value === "—") return null;
    if (type === "num") {
      const parsed = Number(value.replace(/[%,$\s]/g, ""));
      return Number.isNaN(parsed) ? null : parsed;
    }
    if (type === "date") {
      const parsed = Date.parse(value);
      return Number.isNaN(parsed) ? null : parsed;
    }
    return value.toLocaleLowerCase();
  }

  function makeDomTableSortable(table) {
    if (!table || table.dataset.sortBound === "true") {
      return;
    }
    const tbody = table.querySelector("tbody");
    const headers = Array.from(table.querySelectorAll("thead th"));
    if (!tbody || !headers.length) return;

    let sortIndex = null;
    let sortDir = 1;
    table.classList.add("sortable-table");
    table.dataset.sortBound = "true";

    function paint(index) {
      const rows = Array.from(tbody.querySelectorAll("tr"));
      const type = headers[index].dataset.type || detectTableColumnType(rows, index);
      rows.sort((a, b) => {
        const av = comparableTableValue(tableCellText(a, index), type);
        const bv = comparableTableValue(tableCellText(b, index), type);
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        if (type === "num" || type === "date") return (av - bv) * sortDir;
        return (
          String(av).localeCompare(String(bv), undefined, {
            numeric: true,
            sensitivity: "base",
          }) * sortDir
        );
      });
      for (const row of rows) tbody.appendChild(row);
      for (const h of headers) {
        const arrow = h.querySelector(".arrow");
        if (headers.indexOf(h) === index) {
          h.classList.add("sorted");
          if (arrow) arrow.textContent = sortDir === 1 ? " ▲" : " ▼";
        } else {
          h.classList.remove("sorted");
          if (arrow) arrow.textContent = "";
        }
      }
    }

    function sortBy(index) {
      const rows = Array.from(tbody.querySelectorAll("tr"));
      const type = headers[index].dataset.type || detectTableColumnType(rows, index);
      if (sortIndex === index) sortDir *= -1;
      else {
        sortIndex = index;
        sortDir = type === "str" ? 1 : -1;
      }
      paint(index);
    }

    headers.forEach((header, index) => {
      if (!header.querySelector(".arrow")) {
        header.appendChild(el("span", { class: "arrow" }));
      }
      header.setAttribute("tabindex", "0");
      header.setAttribute("role", "button");
      header.addEventListener("click", () => sortBy(index));
      header.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        sortBy(index);
      });
    });
  }

  // Prose tables are authored evidence inside a finding — a few rows in a fixed,
  // meaningful order. Sorting them is noise, so only the generated appendix and
  // section tables get the sort affordance.
  function makeTablesSortable() {
    for (const table of $$("table")) {
      if (table.classList.contains("prose-table")) continue;
      makeDomTableSortable(table);
    }
  }

  function buildYearlyChart(dora) {
    const node = $("#yearlyChart");
    if (!node) return;
    const years = Object.keys(dora.commits_per_year);
    if (node._chart) node._chart.dispose();
    const chart = echarts.init(node, null, { renderer: "svg" });
    node._chart = chart;
    const t = chartTheme();
    chart.setOption({
      animation: false,
      tooltip: {
        trigger: "axis",
        backgroundColor: "#0A2540",
        borderWidth: 0,
        textStyle: { color: "#fff" },
      },
      legend: {
        data: ["Commits", "Merges", "PR merges"],
        textStyle: { color: t.ink, fontFamily: "Raleway, sans-serif" },
      },
      grid: { left: 56, right: 24, top: 36, bottom: 32, containLabel: false },
      xAxis: {
        type: "category",
        data: years,
        axisLabel: { color: t.mute },
        axisLine: { lineStyle: { color: t.rule } },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: t.mute },
        axisLine: { lineStyle: { color: t.rule } },
        splitLine: { lineStyle: { color: t.ruleSoft } },
      },
      series: [
        {
          name: "Commits",
          type: "bar",
          data: years.map((y) => dora.commits_per_year[y] || 0),
          itemStyle: { color: t.teal },
        },
        {
          name: "Merges",
          type: "bar",
          data: years.map((y) => dora.merges_per_year[y] || 0),
          itemStyle: { color: t.blue },
        },
        {
          name: "PR merges",
          type: "line",
          smooth: true,
          data: years.map((y) => dora.pr_merges_per_year[y] || 0),
          itemStyle: { color: "#D9531E" },
          lineStyle: { color: "#D9531E", width: 2 },
          symbol: "circle",
          symbolSize: 6,
        },
      ],
    });
    attachChartResize(node);
  }

  function buildCommitSizeChart(rows) {
    const node = $("#commitSizeChart");
    if (!node) return;
    if (node._chart) node._chart.dispose();
    const chart = echarts.init(node, null, { renderer: "svg" });
    node._chart = chart;
    const t = chartTheme();
    const months = rows.map((r) => r.month);
    const adds = rows.map((r) => r.additions);
    // Render deletions as negative numbers so the bars diverge cleanly above /
    // below the x-axis. The tooltip and axis labels show absolute values.
    const dels = rows.map((r) => -Math.abs(r.deletions));
    const meanSz = rows.map((r) => r.mean_size);
    chart.setOption({
      animation: false,
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "#0A2540",
        borderWidth: 0,
        textStyle: { color: "#fff" },
        formatter: (params) => {
          const m = params[0]?.axisValue || "";
          let html = `<b>${m}</b>`;
          for (const p of params) {
            const v = p.seriesName === "Lines removed" ? Math.abs(p.value) : p.value;
            html += `<br/>${p.marker} ${p.seriesName}: <b>${Number(v).toLocaleString()}</b>`;
          }
          return html;
        },
      },
      legend: {
        data: ["Lines added", "Lines removed", "Mean commit size"],
        textStyle: { color: t.ink, fontFamily: "Raleway, sans-serif" },
      },
      grid: { left: 70, right: 64, top: 36, bottom: 32, containLabel: false },
      xAxis: {
        type: "category",
        data: months,
        axisLabel: { color: t.mute, fontFamily: "Raleway, sans-serif" },
        axisLine: { lineStyle: { color: t.rule } },
      },
      yAxis: [
        {
          type: "value",
          name: "Lines",
          nameTextStyle: { color: t.mute, fontFamily: "Raleway, sans-serif" },
          axisLabel: {
            color: t.mute,
            fontFamily: "Raleway, sans-serif",
            formatter: (v) => Math.abs(v).toLocaleString(),
          },
          splitLine: { lineStyle: { color: t.ruleSoft } },
          axisLine: { lineStyle: { color: t.rule } },
        },
        {
          type: "value",
          name: "Mean size",
          position: "right",
          nameTextStyle: { color: t.mute, fontFamily: "Raleway, sans-serif" },
          axisLabel: { color: t.mute, fontFamily: "Raleway, sans-serif" },
          splitLine: { show: false },
          axisLine: { lineStyle: { color: t.rule } },
        },
      ],
      series: [
        {
          name: "Lines added",
          type: "bar",
          stack: "loc",
          data: adds,
          itemStyle: { color: t.teal },
        },
        {
          name: "Lines removed",
          type: "bar",
          stack: "loc",
          data: dels,
          itemStyle: { color: "#D9531E" },
        },
        {
          name: "Mean commit size",
          type: "line",
          yAxisIndex: 1,
          smooth: true,
          data: meanSz,
          lineStyle: { color: t.blue, width: 2 },
          itemStyle: { color: t.blue },
          symbol: "circle",
          symbolSize: 5,
        },
      ],
    });
    attachChartResize(node);
  }

  // Module-scoped state so theme changes / dimension toggles preserve the
  // user's scrub position and current dimension.
  let _raceCurrentIdx = null;
  let _raceDimension = "commits"; // "commits" | "loc"
  // Playback timer is module-scoped so a rebuild (theme toggle, dimension
  // switch) can stop the PREVIOUS build's interval. Left running, it kept
  // calling setOption on the chart the rebuild had already disposed.
  let _raceTimer = null;

  function buildRaceChart(rc) {
    const node = $("#raceChart");
    if (!node) return;
    if (_raceTimer) {
      clearInterval(_raceTimer);
      _raceTimer = null;
    }
    const months = rc.months || [];
    if (!months.length) return;
    // Pick the series matching the current dimension (fall back to commits).
    const sourceSeries =
      _raceDimension === "loc" && rc.loc_series ? rc.loc_series : rc.series;
    const authors = Object.keys(sourceSeries);
    if (node._chart) node._chart.dispose();
    const chart = echarts.init(node, null, { renderer: "svg" });
    node._chart = chart;
    const colorOf = (i) => RACE_PALETTE[i % RACE_PALETTE.length];

    const yAxisLabel =
      _raceDimension === "loc" ? "Cumulative lines changed" : "Cumulative commits";
    const fmtVal = (v) =>
      _raceDimension === "loc" && v != null ? Number(v).toLocaleString() : v;

    function frame(idx) {
      const t = chartTheme();
      const visible = months.slice(0, idx + 1);
      const series = authors
        .map((a, i) => {
          const sliced = sourceSeries[a].slice(0, idx + 1);
          let lastVal = null,
            lastIdx = -1;
          for (let j = sliced.length - 1; j >= 0; j--) {
            if (sliced[j] != null) {
              lastVal = sliced[j];
              lastIdx = j;
              break;
            }
          }
          if (lastIdx < 0) return null;
          let totalLastIdx = -1;
          for (let j = sourceSeries[a].length - 1; j >= 0; j--) {
            if (sourceSeries[a][j] != null) {
              totalLastIdx = j;
              break;
            }
          }
          const hasStopped =
            lastIdx === totalLastIdx && lastIdx < months.length - 1 && lastIdx <= idx;
          return {
            name: a,
            type: "line",
            showSymbol: false,
            connectNulls: false,
            smooth: false,
            lineStyle: { width: 2, color: colorOf(i) },
            emphasis: { focus: "series", lineStyle: { width: 3.5 } },
            endLabel: {
              show: true,
              color: colorOf(i),
              formatter: () => (hasStopped ? "■ " : "") + a + ": " + fmtVal(lastVal),
              fontWeight: 700,
              fontFamily: "Raleway, sans-serif",
              fontSize: 11,
            },
            markPoint: hasStopped
              ? {
                  symbol: "circle",
                  symbolSize: 7,
                  itemStyle: {
                    color: colorOf(i),
                    borderColor: t.paper,
                    borderWidth: 1,
                  },
                  label: { show: false },
                  data: [{ coord: [visible[lastIdx], lastVal] }],
                }
              : undefined,
            data: sliced.map((v, j) => [visible[j], v]),
          };
        })
        .filter(Boolean);
      return {
        animation: false,
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "cross" },
          backgroundColor: "#0A2540",
          borderWidth: 0,
          textStyle: { color: "#fff" },
        },
        grid: { left: 56, right: 200, top: 30, bottom: 36, containLabel: false },
        xAxis: {
          type: "category",
          data: months,
          boundaryGap: false,
          axisLabel: { color: t.mute, fontFamily: "Raleway, sans-serif" },
          axisLine: { lineStyle: { color: t.rule } },
        },
        yAxis: {
          type: "value",
          name: yAxisLabel,
          nameTextStyle: { color: t.mute, fontFamily: "Raleway, sans-serif" },
          axisLabel: {
            color: t.mute,
            fontFamily: "Raleway, sans-serif",
            formatter: (v) => Number(v).toLocaleString(),
          },
          splitLine: { lineStyle: { color: t.ruleSoft } },
          axisLine: { lineStyle: { color: t.rule } },
        },
        graphic: [
          {
            type: "text",
            right: 220,
            top: 6,
            style: {
              text: months[idx],
              fontSize: 28,
              fontWeight: 700,
              fill: isDarkMode() ? "rgba(230,237,243,0.10)" : "rgba(5,56,91,0.10)",
              fontFamily: "Raleway, sans-serif",
            },
          },
        ],
        animationDurationUpdate: 250,
        animationEasingUpdate: "linear",
        series,
      };
    }

    const scrub = $("#raceScrub");
    const nowLabel = $("#raceNowLabel");
    const playBtn = $("#racePlay");
    const resetBtn = $("#raceReset");
    scrub.max = months.length - 1;
    // Restore prior scrub position (e.g. after a theme toggle re-render).
    const startIdx =
      _raceCurrentIdx != null
        ? Math.max(0, Math.min(months.length - 1, _raceCurrentIdx))
        : months.length - 1;
    scrub.value = startIdx;
    let idx = startIdx;
    let playing = false;

    function paint(i) {
      idx = i;
      _raceCurrentIdx = i;
      scrub.value = i;
      nowLabel.textContent = months[i];
      chart.setOption(frame(i), { notMerge: true });
    }
    function play() {
      if (playing) {
        stop();
        return;
      }
      playing = true;
      playBtn.innerHTML = "&#10074;&#10074; Pause";
      if (idx >= months.length - 1) idx = 0;
      _raceTimer = setInterval(() => {
        if (idx >= months.length - 1) {
          stop();
          return;
        }
        paint(idx + 1);
      }, 150);
    }
    function stop() {
      playing = false;
      playBtn.innerHTML = "&#9654; Play";
      if (_raceTimer) clearInterval(_raceTimer);
      _raceTimer = null;
    }
    function onReset() {
      stop();
      paint(0);
    }
    function onScrub(ev) {
      stop();
      paint(Number(ev.target.value));
    }
    // Every rebuild produces fresh closures bound to the new chart instance, so
    // the PREVIOUS build's handlers must come off first. Without this, one
    // theme toggle left two Play handlers on the button — a second click
    // started a second interval and the two fought over the scrub position.
    const prev = node._controls;
    if (prev) {
      playBtn.removeEventListener("click", prev.play);
      resetBtn.removeEventListener("click", prev.reset);
      scrub.removeEventListener("input", prev.scrub);
    }
    node._controls = { play, reset: onReset, scrub: onScrub };
    playBtn.addEventListener("click", play);
    resetBtn.addEventListener("click", onReset);
    scrub.addEventListener("input", onScrub);

    // Dimension toggle (Commits / LoC). Each click stops playback, updates
    // the chip pressed-state, and re-renders the whole race chart from rc.
    function setDim(d) {
      if (d === _raceDimension) return;
      _raceDimension = d;
      stop();
      for (const b of $$(".race-dim-btn")) {
        const active = b.dataset.dim === d;
        b.classList.toggle("is-active", active);
        b.setAttribute("aria-checked", active ? "true" : "false");
      }
      buildRaceChart(rc);
    }
    const commitsBtn = $("#raceDimCommits");
    const locBtn = $("#raceDimLoc");
    if (commitsBtn && !commitsBtn._wired) {
      commitsBtn.addEventListener("click", () => setDim("commits"));
      commitsBtn._wired = true;
    }
    if (locBtn && !locBtn._wired) {
      locBtn.addEventListener("click", () => setDim("loc"));
      locBtn._wired = true;
    }
    // Reflect current dim in button state in case of re-entry from a theme change.
    for (const b of $$(".race-dim-btn")) {
      const active = b.dataset.dim === _raceDimension;
      b.classList.toggle("is-active", active);
      b.setAttribute("aria-checked", active ? "true" : "false");
    }

    paint(startIdx);
    attachChartResize(node);
  }

  // ---------- Theme toggle (light / dark) -----------------------------------

  const THEME_KEY = "zenable-report-theme";

  function isDarkMode() {
    if (document.body.classList.contains("print-light-render")) return false;
    return document.documentElement.dataset.theme === "dark";
  }
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    const btn = $("#themeToggle");
    if (btn) {
      // Show the icon for the mode you'd switch TO.
      btn.textContent = theme === "dark" ? "☼" : "☽"; // ☼ vs ☽
      btn.setAttribute(
        "aria-label",
        theme === "dark" ? "Switch to light mode" : "Switch to dark mode",
      );
      btn.setAttribute(
        "title",
        theme === "dark" ? "Switch to light mode" : "Switch to dark mode",
      );
    }
  }
  function initTheme() {
    let saved = null;
    try {
      saved = localStorage.getItem(THEME_KEY);
    } catch (e) {}
    if (saved !== "dark" && saved !== "light") {
      saved =
        window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light";
    }
    applyTheme(saved);
  }
  function toggleTheme() {
    const next = isDarkMode() ? "light" : "dark";
    applyTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (e) {}
    rerenderCharts();
  }
  function rerenderCharts() {
    // ECharts options bake in colors at setOption time, so a theme change
    // requires re-rendering each chart from its source data.
    try {
      renderHeatmap();
    } catch (e) {
      console.warn("heatmap rerender", e);
    }
    // mermaid bakes theme colors at render time too, so re-run it on toggle.
    try {
      renderTrustBoundary();
    } catch (e) {
      console.warn("trust diagram rerender", e);
    }
    const data = loadMetricsData();
    if (data) {
      if (data.dora) {
        try {
          buildYearlyChart(data.dora);
        } catch (e) {}
      }
      if (data.racing_chart) {
        try {
          buildRaceChart(data.racing_chart);
        } catch (e) {}
      }
      if (data.loc_per_month) {
        try {
          buildCommitSizeChart(data.loc_per_month);
        } catch (e) {}
      }
    }
  }

  // Print renderers bake colors into SVG/canvas. Use a print-only render mode
  // so PDFs are light without changing the user's saved screen theme.
  let _printMode = "full";

  const SUMMARY_OMITTED_SECTIONS = [
    "#samm",
    "#strengths",
    "#heatmap",
    "#findings",
    "#cves",
    "#customRequirements",
    "#recs",
  ];
  function findTocEntry(href) {
    const link = $$(".toc a[href]").find((candidate) => {
      return candidate.getAttribute("href") === href;
    });
    if (!link) return null;
    return {
      num: $(".toc-num", link)?.textContent.trim() || "",
      title: $(".toc-text", link)?.textContent.trim() || link.textContent.trim(),
    };
  }

  function targetExists(href) {
    if (!href || !href.startsWith("#")) return false;
    return Boolean(document.getElementById(href.slice(1)));
  }

  // Drop TOC cards/links (and emptied groups) whose target section isn't present.
  function pruneDeadNavLinks() {
    $$(".toc a[href^='#']").forEach((link) => {
      const href = link.getAttribute("href") || "";
      if (href === "#") return;
      if (document.getElementById(decodeURIComponent(href.slice(1)))) return;
      (link.closest("li") || link).remove();
    });
    $$(".toc-list").forEach((list) => {
      if (!list.querySelector("li")) {
        const group = list.closest(".toc-group");
        (group || list).remove();
      }
    });
  }

  // Remove data-driven sections that rendered with no content (e.g. an empty
  // "Possible (Unconfirmed) Findings" appendix). Runs before pruneDeadNavLinks
  // so the now-missing section's TOC card is dropped too.
  function pruneEmptySections() {
    const rules = [["#appendix-unconfirmed", "#unconfirmedList"]];
    for (const [sec, list] of rules) {
      const section = $(sec);
      const container = $(list);
      if (section && container && container.children.length === 0) section.remove();
    }
  }

  // Re-letter appendices A,B,C... by document order so pruning/reordering never
  // leaves gaps. The section id slug (e.g. `appendix-deps`) is the STABLE key; the
  // displayed letter is positional. Returns idSuffix -> letter.
  function numberAppendices() {
    const map = {};
    $$('section[id^="appendix-"]').forEach((sec, i) => {
      const letter = String.fromCharCode(65 + i);
      map[sec.id.slice("appendix-".length)] = letter;
      const h = sec.querySelector("h2");
      if (h)
        h.textContent = h.textContent.replace(
          /^Appendix\s+[A-Za-z0-9]+/,
          "Appendix " + letter,
        );
      const num = $(`.toc a[href="#${sec.id}"] .toc-num`);
      if (num) num.textContent = letter;
    });
    return map;
  }

  // Resolve stable appendix references to their positional letter + link.
  // `{{appendix:<idSuffix>}}` tokens in prose and `a.appendix-ref[data-appendix]`
  // both become "Appendix <letter>" linking to the section; refs to a pruned
  // appendix are dropped so we never point at something that isn't there.
  function resolveAppendixRefs(map) {
    const makeLink = (slug) => {
      const a = document.createElement("a");
      a.className = "appendix-ref";
      a.href = `#appendix-${slug}`;
      a.textContent = `Appendix ${map[slug]}`;
      return a;
    };
    $$("a.appendix-ref[data-appendix]").forEach((a) => {
      const slug = a.getAttribute("data-appendix");
      if (map[slug]) {
        a.textContent = `Appendix ${map[slug]}`;
        a.setAttribute("href", `#appendix-${slug}`);
      } else {
        a.remove();
      }
    });
    const re = /\{\{appendix:([a-z0-9-]+)\}\}/g;
    const root = $("main") || document.body;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const hits = [];
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (n.nodeValue.indexOf("{{appendix:") !== -1) hits.push(n);
    }
    hits.forEach((node) => {
      const s = node.nodeValue;
      const frag = document.createDocumentFragment();
      let last = 0;
      let m;
      re.lastIndex = 0;
      while ((m = re.exec(s))) {
        if (m.index > last)
          frag.appendChild(document.createTextNode(s.slice(last, m.index)));
        if (map[m[1]]) frag.appendChild(makeLink(m[1]));
        last = m.index + m[0].length;
      }
      if (last < s.length) frag.appendChild(document.createTextNode(s.slice(last)));
      node.parentNode.replaceChild(frag, node);
    });
  }

  function hasAttackPathsSection() {
    return Boolean($(".attack-block"));
  }

  function appendSummaryOmittedItem(root, item) {
    root.appendChild(
      el("article", { class: "summary-omitted-item" }, [
        el("span", { class: "summary-omitted-num", text: item.num }),
        el("span", { class: "summary-omitted-title", text: item.title }),
      ]),
    );
  }

  function appendSummaryOmittedItems(root, items) {
    const rows = Math.ceil(items.length / 2);
    for (let row = 0; row < rows; row += 1) {
      appendSummaryOmittedItem(root, items[row]);
      const right = items[row + rows];
      if (right) appendSummaryOmittedItem(root, right);
    }
  }

  function buildSummaryOmittedSections() {
    const wrap = $("#summaryOmitted");
    const grid = $("#summaryOmittedGrid");
    if (!wrap || !grid) return;
    grid.innerHTML = "";
    const items = [];

    if (hasAttackPathsSection()) {
      const trust = findTocEntry("#trust");
      items.push({
        num: trust?.num || "3",
        title: "Attack paths",
      });
    }

    for (const href of SUMMARY_OMITTED_SECTIONS) {
      if (!targetExists(href)) continue;
      const entry = findTocEntry(href);
      if (entry) items.push(entry);
    }

    const appendixHrefs = $$(".toc-list--appendix a[href]").map((a) =>
      a.getAttribute("href"),
    );
    for (const href of appendixHrefs) {
      if (!targetExists(href)) continue;
      const entry = findTocEntry(href);
      if (entry) items.push(entry);
    }

    appendSummaryOmittedItems(grid, items);
    wrap.hidden = grid.children.length === 0;
  }

  function onBeforePrint() {
    if (!document.body.classList.contains("print-light-render")) {
      document.body.classList.add("print-light-render");
      rerenderCharts();
    }
  }
  function onAfterPrint() {
    if (document.body.classList.contains("print-light-render")) {
      document.body.classList.remove("print-light-render");
      rerenderCharts();
    }
    _printMode = "full";
    document.body.classList.remove("print-summary");
  }

  async function printReport(mode) {
    _printMode = mode === "summary" ? "summary" : "full";
    if (_printMode === "summary") buildSummaryOmittedSections();
    document.body.classList.toggle("print-summary", _printMode === "summary");
    // Apply the light print palette and FINISH the async chart/diagram render
    // before printing. mermaid.run is async, so printing mid-render yields a
    // blank diagram; the heatmap must also re-init at the print box size. Doing
    // this here (and awaiting) means onBeforePrint is a no-op (class already set)
    // and the snapshot is taken only once everything is ready.
    const addedPrintRender = !document.body.classList.contains("print-light-render");
    if (addedPrintRender) document.body.classList.add("print-light-render");
    try {
      renderHeatmap();
    } catch (e) {
      console.warn("print heatmap render", e);
    }
    try {
      await renderTrustBoundary();
    } catch (e) {
      console.warn("print trust diagram render", e);
    }
    // Let layout settle at print dimensions before the snapshot.
    await new Promise((resolve) => setTimeout(resolve, 60));
    window.print();
  }

  function onParentMessage(event) {
    const data = event.data;
    if (event.source !== window.parent) return;
    if (!data || typeof data !== "object") return;
    if (data.type !== "report:print") return;
    if (!window.__ZENABLE_REPORT_NONCE__) return;
    if (data.nonce !== window.__ZENABLE_REPORT_NONCE__) return;
    printReport(data.mode);
  }

  function postParentMessage(message) {
    const nonce = window.__ZENABLE_REPORT_NONCE__;
    if (!nonce || window.parent === window) return;
    try {
      const parentOrigin = new URL(window.__ZENABLE_PARENT_ORIGIN__).origin;
      window.parent.postMessage(Object.assign({ nonce: nonce }, message), parentOrigin);
    } catch (e) {}
  }

  function bindDownloadBridge() {
    if (window.__ZENABLE_DOWNLOAD_BRIDGE_INSTALLED__) return;
    if (!window.__ZENABLE_REPORT_NONCE__ || window.parent === window) return;
    window.__ZENABLE_DOWNLOAD_BRIDGE_INSTALLED__ = true;
    document.addEventListener("click", (event) => {
      const target = event.target;
      const link =
        target && target.closest
          ? target.closest("[data-download-kind][data-download-path]")
          : null;
      if (!link) return;
      const kind = link.getAttribute("data-download-kind");
      const path = link.getAttribute("data-download-path");
      if (kind !== "context" && kind !== "evidence" && kind !== "experiment") return;
      if (!path) return;
      event.preventDefault();
      postParentMessage({ type: "report:download", kind: kind, path: path });
    });
  }

  // ---------- boot ----------------------------------------------------------

  // Sections are opt-out at populate time — removing a <section> from
  // index.html (and emptying the matching field in data.js) is a supported
  // workflow. Renderers that touch a removed container would otherwise throw
  // and abort the rest of the boot sequence, so each call is sandboxed.
  function safeRender(name, fn) {
    try {
      fn();
    } catch (err) {
      if (window.console && console.warn) {
        console.warn(`[zenable-assessment] skipped ${name}: ${err && err.message}`);
      }
    }
  }

  // The chart libraries are the report's ONLY remote resources, and they are
  // loaded dynamically — never via static <script src> tags. A static classic
  // script BLOCKS the HTML parser, so a network middlebox that accepts the
  // request and never answers (corporate TLS-inspection gateways do this)
  // would wedge the entire report before any inline script runs. Dynamic
  // loading keeps hydration independent of chart delivery: boot waits at most
  // CHART_LIB_WAIT_MS, renders chart-less if needed, and fills the charts in
  // when a slow library finally lands.
  //
  // The version + SRI pins here are a MIRROR of what the hosting app serves at
  // these immutable, versioned URLs; that side owns the pin. Bump it there
  // first, then mirror the version + integrity into this list. A mismatch means
  // the browser blocks the script on SRI and the hosted report silently loses
  // its charts.
  //
  // `path` is deliberately one whole literal string rather than assembled from
  // a filename at the point of use. Asset-retention tooling decides which
  // versions are still needed by scanning already-issued report.html files for
  // this exact `report-assets/<name>-<semver>.min.js` shape; a version it
  // cannot see there looks unreferenced and becomes eligible for removal, which
  // would 404 the pinned URL those issued reports depend on. Keep it literal.
  const CHART_LIBS = [
    {
      global: "echarts",
      path: "report-assets/echarts-5.6.1.min.js",
      integrity:
        "sha384-pPi0zxBAoDu6+JXW/C68UZLvBUUtU+7zonhif43rqj7pxsGyqyqzcian2Rj37Rss",
    },
    {
      global: "mermaid",
      path: "report-assets/mermaid-11.15.0.min.js",
      integrity:
        "sha384-yQ4mmBBT+vhTAwjFH0toJXNYJ6O4usWnt6EPIdWwrRvx2V/n5lXuDZQwQFeSFydF",
    },
  ];
  const CHART_LIB_WAIT_MS = 8000;

  // A `file://` page cannot satisfy Subresource Integrity: the response is
  // opaque, so the browser has nothing to hash and BLOCKS the script outright —
  // and `crossOrigin` turns the same load into a CORS failure. Passing a null
  // integrity omits both attributes, which is the only way a local vendored
  // copy loads at all. That copy's bytes are verified against this same pin
  // when `fetch_chart_libs.py` downloads it, so the pin is still enforced —
  // just at vendor time instead of load time.
  function loadScript(src, integrity) {
    return new Promise((resolve) => {
      const s = document.createElement("script");
      s.src = src;
      s.async = true;
      if (integrity) {
        s.integrity = integrity;
        s.crossOrigin = "anonymous";
      }
      s.onload = () => resolve(true);
      s.onerror = () => resolve(false);
      document.head.appendChild(s);
    });
  }

  // AT RUNTIME (hosted on *.zenable.app, or inside the app's srcdoc viewer
  // iframe, whose base URL is the app origin) the root-relative URL resolves to
  // the pinned same-origin asset and SRI is enforced by the browser. That is
  // always attempt 1, so a hosted report never reads a vendored copy.
  //
  // Opened LOCALLY from file:// there is no origin to resolve `/report-assets/`
  // against, so attempt 2 reads the copy vendored NEXT TO the report by
  // `scripts/fetch_chart_libs.py` (report/report-assets/) — offline-capable
  // local review, no network round trip, no SRI (see loadScript). Attempt 3 is
  // the last resort for a local report with no vendored copy: the SAME pinned
  // file over https from the matching environment, <sub> =
  // window.__ZENABLE_SUBDOMAIN__ or "www", with SRI enforced.
  async function loadChartLib(lib) {
    if (window[lib.global]) return true;
    const isFile = window.location && window.location.protocol === "file:";
    // Branch rather than try both: a root-relative URL on file:// resolves to
    // file:///report-assets/… and is rejected as a cross-origin request, which
    // prints two CORS errors per library into the console of the very local
    // review this path exists to support.
    if (isFile) {
      await loadScript(lib.path, null);
    } else {
      await loadScript(`/${lib.path}`, lib.integrity);
    }
    if (window[lib.global]) return true;
    const sub = (window.__ZENABLE_SUBDOMAIN__ || "").trim() || "www";
    await loadScript(`https://${sub}.zenable.app/${lib.path}`, lib.integrity);
    return Boolean(window[lib.global]);
  }

  async function ensureChartLibs() {
    const pending = CHART_LIBS.filter((lib) => !window[lib.global]);
    if (!pending.length) return;
    const loads = Promise.all(pending.map(loadChartLib));
    const timedOut = await Promise.race([
      loads.then(() => false),
      new Promise((resolve) => {
        setTimeout(() => resolve(true), CHART_LIB_WAIT_MS);
      }),
    ]);
    // Late arrival: the download outlived the bounded wait but may still
    // finish. Re-render the chart surfaces once it does — everything else
    // already hydrated without it.
    if (timedOut) {
      loads.then(() => {
        if (pending.some((lib) => window[lib.global])) {
          clearChartsUnavailable();
          rerenderCharts();
        }
      });
    }
  }

  async function boot() {
    initTheme();
    safeRender("warnLiteralDisplayIds", warnLiteralDisplayIds);
    bind();
    await ensureChartLibs();
    safeRender("renderSummary", renderSummary);
    safeRender("renderScope", renderScope);
    safeRender("renderTrustBoundary", renderTrustBoundary);
    safeRender("renderAttackPaths", renderAttackPaths);
    safeRender("renderSamm", renderSamm);
    safeRender("renderStrengths", renderStrengths);
    safeRender("renderHeatmap", renderHeatmap);
    safeRender("renderFindings", renderFindings);
    safeRender("renderCves", renderCves);
    safeRender("renderCustomRequirements", renderCustomRequirements);
    safeRender("renderRecs", renderRecs);
    safeRender("renderInvestigator", renderInvestigator);
    safeRender("renderAppendices", renderAppendices);
    safeRender("renderDependencies", renderDependencies);
    safeRender("renderRepoMetrics", renderRepoMetrics);
    safeRender("renderExtensionAppendices", renderExtensionAppendices);
    safeRender("buildSummaryOmittedSections", buildSummaryOmittedSections);
    safeRender("makeTablesSortable", makeTablesSortable);

    const themeBtn = $("#themeToggle");
    if (themeBtn) themeBtn.addEventListener("click", toggleTheme);
    // srcdoc iframe inherits the parent base URL, so native `#anchor` clicks try
    // to navigate the frame (X-Frame-Options: DENY) instead of scrolling. Always
    // preventDefault and scroll via JS; `href="#"` downloads go to the bridge.
    document.addEventListener("click", (event) => {
      const closest = event.target.closest;
      if (!closest) return;
      const link = event.target.closest('a[href^="#"]');
      if (!link) return;
      const href = link.getAttribute("href") || "";
      if (href === "#" || link.hasAttribute("data-download-kind")) return;
      event.preventDefault();
      const findingId =
        link.dataset.findingId ||
        (href.startsWith("#finding-") ? href.slice("#finding-".length) : "");
      if (findingId) {
        jumpToFinding(findingId);
        return;
      }
      const target = document.getElementById(decodeURIComponent(href.slice(1)));
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    pruneEmptySections();
    pruneDeadNavLinks();
    resolveAppendixRefs(numberAppendices());
    bindDownloadBridge();

    window.addEventListener("beforeprint", onBeforePrint);
    window.addEventListener("afterprint", onAfterPrint);
    if (!window.__ZENABLE_PRINT_BRIDGE_INSTALLED__) {
      window.__ZENABLE_PRINT_BRIDGE_INSTALLED__ = true;
      window.addEventListener("message", onParentMessage);
    }
    const mq = window.matchMedia && window.matchMedia("print");
    if (mq && mq.addEventListener) {
      mq.addEventListener("change", (e) =>
        e.matches ? onBeforePrint() : onAfterPrint(),
      );
    }
  }

  // Test seam. The harness defines window.__ZENABLE_TEST_HOOK__ *before*
  // loading app.js and receives the real internals; a published report never
  // defines it, so this is inert in every browser that opens one. Exporting the
  // functions rather than reimplementing them in the test is the whole point —
  // a test that re-derives the markdown pipeline proves nothing about the
  // pipeline the report actually runs.
  if (typeof window.__ZENABLE_TEST_HOOK__ === "function") {
    window.__ZENABLE_TEST_HOOK__({
      renderInline,
      renderProse,
      splitTableRow,
      tableAlignments,
      escapeHtml,
      cleanDownloadPath,
      normalizeFindingSeverity,
      likelihoodScoreOf,
      impactScoreOf,
      bucketOf,
      zoneOf,
      severityFromCvss,
      didForKey,
      refTitle,
      findLiteralDisplayIds,
      loadChartLib,
      ensureChartLibs,
      CHART_LIBS,
      FINDINGS_ORDERED,
      STRENGTHS_ORDERED,
      RECS_ORDERED,
      ATTACKS_ORDERED,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
