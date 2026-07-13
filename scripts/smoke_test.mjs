// Headless boot + behaviour smoke test, run in CI on every pull request
// (.github/workflows/smoke-test.yml). Serves the real index.html and drives it
// in Chromium via Playwright.
//
// THREAD 1 scope (METRO_EXPANSION_PLAYBOOK §8/§10): five layers are registered —
// Neighborhood, ZIP, Borough, Judicial District, Municipal Court. The three
// offline anchors (borough / judicial-district / municipal-court) ship as
// same-origin data/app/*.json, so this test classifies a known point against
// them without depending on any third-party API being up in CI. It also
// exercises the NYC water-click honesty rule (a mid-river click resolves to no
// borough) and per-layer failure isolation. EXPECT_LAYERS climbs to 24 by
// Thread 6; the neighborhood/ZIP layers are live-Socrata and are deliberately
// NOT asserted as ground truth (flaky/throttled in CI).
//
// Run locally against a static server:
//     python3 -m http.server 8000 &
//     npm install playwright && node scripts/smoke_test.mjs
// Configure the URL with BASE_URL (default http://localhost:8000/).

import { chromium } from "playwright";
import { readFileSync, existsSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

// Vendored Leaflet fallback for sandboxed environments (e.g. Claude Code web),
// where the browser (Chromium) cannot reach cdnjs.cloudflare.com — it does not
// use the agent HTTPS proxy, so the request resets and the app never boots
// ("L is not defined"). scripts/vendor_leaflet.sh populates this dir via curl,
// which *can* reach the CDN through the proxy; when present we serve Leaflet
// same-origin below so the app boots. Absent (production, GitHub Actions CI)
// the browser loads Leaflet straight from the CDN exactly as before.
const VENDOR_DIR = join(dirname(fileURLToPath(import.meta.url)), "vendor", "leaflet");
const VENDORED_LEAFLET =
  existsSync(join(VENDOR_DIR, "leaflet.js")) && existsSync(join(VENDOR_DIR, "leaflet.css"))
    ? { js: readFileSync(join(VENDOR_DIR, "leaflet.js")), css: readFileSync(join(VENDOR_DIR, "leaflet.css")) }
    : null;
if (VENDORED_LEAFLET) console.log("  (serving Leaflet from scripts/vendor/leaflet — CDN unreachable in this env)");

const BASE = process.env.BASE_URL || "http://localhost:8000/";
// ==== GENERATED:BEGIN smoke-config ====
const POINT = "40.71274,-74.00602"; // New York City Hall (Manhattan)
const OFFLINE = ["borough", "judicial-district", "municipal-court"];
const EXPECT_DISTRICT = { "borough": "Brooklyn", "judicial-district": "1", "municipal-court": "1" };
const NEGATIVE_POINT = "40.72230,-73.96970"; // mid-East-River — legitimately no borough
const EXPECT_LAYERS = 24; // Threads 1–4: full roster (+ council, community-district, congress, state senate/assembly, election-district, borough-president, district-attorney)
// ==== GENERATED:END smoke-config ====
const POINT2 = "40.69354,-73.98963"; // Brooklyn Borough Hall (Brooklyn) — the re-classify hop stays fork test code
const BOOT_TIMEOUT = 45000; // Leaflet CDN + first paint on a cold CI runner
const QUERY_TIMEOUT = 25000;

const failures = [];
function check(name, ok, detail) {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
  if (!ok) failures.push(name);
}

async function booted(context, url, routeFn) {
  const page = await context.newPage();
  if (VENDORED_LEAFLET) {
    await page.route("**/cdnjs.cloudflare.com/**/leaflet.js", (r) =>
      r.fulfill({ status: 200, contentType: "application/javascript", body: VENDORED_LEAFLET.js }));
    await page.route("**/cdnjs.cloudflare.com/**/leaflet.css", (r) =>
      r.fulfill({ status: 200, contentType: "text/css", body: VENDORED_LEAFLET.css }));
  }
  if (routeFn) await routeFn(page);
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => !!window.NycExplorer, null, { timeout: BOOT_TIMEOUT });
  return page;
}

// Wait for a layer card to finish loading, then return its normalized text.
async function cardText(page, id) {
  await page
    .waitForFunction(
      (cid) => {
        const el = document.getElementById("card-" + cid);
        return el && !el.querySelector(".loading-row") &&
          (el.querySelector(".result-fields") || el.querySelector(".state-empty") ||
           el.classList.contains("state-empty") || el.classList.contains("state-error") || el.querySelector(".state-error"));
      },
      id,
      { timeout: QUERY_TIMEOUT }
    )
    .catch(() => {});
  return page.evaluate((cid) => {
    const el = document.getElementById("card-" + cid);
    if (!el) return { text: "(no card)", error: true, empty: false };
    return {
      text: el.innerText.replace(/\s+/g, " ").trim(),
      error: el.classList.contains("state-error") || !!el.querySelector(".state-error"),
      empty: el.classList.contains("state-empty") || !!el.querySelector(".state-empty"),
    };
  }, id);
}

const browser = await chromium.launch();
try {
  // 1. App boots and registers every layer.
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    const page = await booted(context, BASE);
    check("app boots (window.NycExplorer exported)", true);
    const n = await page.evaluate(
      () => document.querySelectorAll('input[type=checkbox][id^="toggle-"]').length
    );
    check(`${EXPECT_LAYERS} layers registered`, n === EXPECT_LAYERS, `found ${n}`);
    await context.close();
  }

  // 2. The three offline anchors classify New York City Hall against known
  //    ground truth, fetched from data/app/*.json (no third-party API).
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    const page = await booted(context, `${BASE}#point=${POINT}&layers=${OFFLINE.join(",")}`);

    const boro = await cardText(page, "borough");
    check(`borough classifies City Hall (${EXPECT_DISTRICT["borough"]})`, !boro.error && new RegExp(EXPECT_DISTRICT["borough"]).test(boro.text) && /New York/.test(boro.text), boro.text.slice(0, 70));

    const jud = await cardText(page, "judicial-district");
    check(`judicial-district classifies City Hall (District ${EXPECT_DISTRICT["judicial-district"]})`, !jud.error && new RegExp("Judicial District\\s*" + EXPECT_DISTRICT["judicial-district"] + "\\b").test(jud.text), jud.text.slice(0, 70));

    const muni = await cardText(page, "municipal-court");
    check(`municipal-court classifies City Hall (${EXPECT_DISTRICT["borough"]} District ${EXPECT_DISTRICT["municipal-court"]})`, !muni.error && new RegExp(EXPECT_DISTRICT["borough"] + " Municipal Court District " + EXPECT_DISTRICT["municipal-court"] + "\\b").test(muni.text), muni.text.slice(0, 80));

    // Moving the selection re-classifies (P7 incremental-restyle fast path):
    // City Hall -> Brooklyn Borough Hall flips borough Manhattan->Brooklyn and
    // judicial district 1->2, and the matched-region highlight must move with it.
    const moved = await page.evaluate(async (p2) => {
      const [lat, lng] = p2.split(",").map(Number);
      window.NycExplorer.setSelectedPoint(lat, lng);
      const boroEl = document.getElementById("card-borough");
      const judEl = document.getElementById("card-judicial-district");
      for (let i = 0; i < 100; i++) {
        if (boroEl && /Brooklyn/.test(boroEl.innerText) && judEl && /Judicial District\s*2\b/.test(judEl.innerText)) break;
        await new Promise((r) => setTimeout(r, 100));
      }
      return {
        boro: boroEl ? boroEl.innerText.replace(/\s+/g, " ").trim() : "(none)",
        jud: judEl ? judEl.innerText.replace(/\s+/g, " ").trim() : "(none)",
        highlights: document.querySelectorAll("#map .nyc-region-highlight").length,
      };
    }, POINT2);
    check(
      "point move re-classifies (Manhattan/1 -> Brooklyn/2) and re-highlights",
      /Brooklyn/.test(moved.boro) && /Judicial District\s*2\b/.test(moved.jud) && moved.highlights >= 1,
      `boro=${moved.boro.slice(0, 30)} | jud=${moved.jud.slice(0, 30)} | highlights=${moved.highlights}`
    );
    await context.close();
  }

  // 3. The NYC water-click honesty rule, made executable: a mid-East-River point
  //    is inside the map bounds but in no shoreline-clipped borough, so the
  //    borough card must show the honest no-result state — never snap to nearest.
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    const page = await booted(context, `${BASE}#point=${NEGATIVE_POINT}&layers=borough`);
    const boro = await cardText(page, "borough");
    check("mid-river click resolves to no borough (honest empty state)", !boro.error && boro.empty, boro.text.slice(0, 70));
    await context.close();
  }

  // 4. A failing data source degrades to that layer's error card + Retry, in
  //    isolation — the app's per-layer failure-isolation rule. Fail the borough
  //    anchor fetch; judicial-district (a different anchor file) still classifies.
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    const page = await booted(
      context,
      `${BASE}#point=${POINT}&layers=borough,judicial-district`,
      (p) => p.route("**/data/app/borough-boundaries.json", (r) => r.fulfill({ status: 503, body: "down" }))
    );
    await page
      .waitForFunction(
        () => {
          const el = document.getElementById("card-borough");
          return el && el.classList.contains("state-error");
        },
        null,
        { timeout: QUERY_TIMEOUT }
      )
      .catch(() => {});
    const res = await page.evaluate(() => {
      const b = document.getElementById("card-borough");
      const j = document.getElementById("card-judicial-district");
      return {
        errored: !!b && b.classList.contains("state-error"),
        hasRetry: !!b && !!b.querySelector(".retry-btn"),
        otherOk: !!j && !j.classList.contains("state-error") && /Judicial District\s*1\b/.test(j.innerText),
      };
    });
    check("failed layer shows error card + Retry", res.errored && res.hasRetry);
    check("failure is isolated (other anchor still classifies)", res.otherOk);
    await context.close();
  }

  // 5. Base-map tile failure surfaces an honest, dismissible banner (R6),
  //    instead of a silently gray map. Pure engine behaviour, no layer data.
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    const page = await booted(context, BASE, (p) =>
      // regex, not a glob: the tile host is `a.basemaps.cartocdn.com` (a dot,
      // not a slash, before `basemaps`), which a `**/basemaps…` glob misses.
      p.route(/basemaps\.cartocdn\.com/, (r) => r.fulfill({ status: 503, body: "down" }))
    );
    await page
      .waitForFunction(() => {
        const el = document.getElementById("tile-banner");
        return el && !el.hidden;
      }, null, { timeout: QUERY_TIMEOUT })
      .catch(() => {});
    const shown = await page.evaluate(() => {
      const el = document.getElementById("tile-banner");
      return !!el && !el.hidden;
    });
    let hiddenAfterDismiss = null;
    if (shown) {
      await page.click("#tile-banner-dismiss");
      hiddenAfterDismiss = await page.evaluate(() => {
        const el = document.getElementById("tile-banner");
        return !!el && el.hidden;
      });
    }
    check("tile failure shows dismissible banner", shown && hiddenAfterDismiss === true, `shown=${shown} hiddenAfterDismiss=${hiddenAfterDismiss}`);
    await context.close();
  }
} finally {
  await browser.close();
}

if (failures.length) {
  console.error(`\n${failures.length} smoke check(s) failed: ${failures.join(", ")}`);
  process.exit(1);
}
console.log("\nAll smoke checks passed.");
