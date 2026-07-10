// Headless boot + behaviour smoke test, run in CI on every pull request
// (.github/workflows/smoke-test.yml). Serves the real index.html and drives it
// in Chromium via Playwright.
//
// THREAD 0 scope (METRO_EXPANSION_PLAYBOOK §10): the NYC fork has been re-cored
// down to the metro-agnostic engine plus a single placeholder "stub" layer, so
// this test asserts only what exists today — the app boots on an NYC map, the
// one stub layer registers, a selected point renders its card, and a base-map
// tile failure surfaces an honest banner. The offline-anchor ground-truth
// checks (classify a known point, per-layer failure isolation) return in
// Thread 1 once the borough / judicial-district / municipal-court static
// anchors land; EXPECT_LAYERS climbs to 24 by Thread 6.
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
const POINT = "40.71274,-74.00602"; // New York City Hall (Manhattan)
const EXPECT_LAYERS = 1; // Thread 0: only the placeholder stub is registered
const BOOT_TIMEOUT = 45000; // Leaflet CDN + first paint on a cold CI runner
const QUERY_TIMEOUT = 25000;

const failures = [];
function check(name, ok, detail) {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
  if (!ok) failures.push(name);
}

// Each check runs in its own context with service workers BLOCKED — the SW is a
// delivery optimization, not what this behaviour test targets, and its cache-
// first serving can defeat the route interception below.
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

const browser = await chromium.launch();
try {
  // 1. App boots and registers every layer (just the stub, in Thread 0).
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    const page = await booted(context, BASE);
    check("app boots (window.NycExplorer exported)", true);
    const n = await page.evaluate(
      () => document.querySelectorAll('input[type=checkbox][id^="toggle-"]').length
    );
    check(`${EXPECT_LAYERS} layer registered`, n === EXPECT_LAYERS, `found ${n}`);
    await context.close();
  }

  // 2. Selecting a point renders the stub layer's card (the engine's
  //    select -> query -> render path). The stub always returns a result, so a
  //    card must appear with the picked coordinate echoed back.
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    const page = await booted(context, `${BASE}#point=${POINT}&layers=stub`);
    await page
      .waitForFunction(
        () => {
          const el = document.getElementById("card-stub");
          return el && !el.querySelector(".loading-row") && /Selected point/i.test(el.innerText);
        },
        null,
        { timeout: QUERY_TIMEOUT }
      )
      .catch(() => {});
    const info = await page.evaluate(() => {
      const el = document.getElementById("card-stub");
      if (!el) return { text: "(no card)", error: true };
      return { text: el.innerText.replace(/\s+/g, " ").trim(), error: el.classList.contains("state-error") };
    });
    check(
      "stub layer renders a card for a selected point",
      !info.error && /Selected point/i.test(info.text) && /40\.71/.test(info.text),
      info.text.slice(0, 80)
    );
    await context.close();
  }

  // 3. Base-map tile failure surfaces an honest, dismissible banner (R6),
  //    instead of a silently gray map. Fail the CARTO tile CDN and assert the
  //    banner appears, then that dismissing it hides it. Pure engine behaviour,
  //    no layer data involved.
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
