# NYC District Explorer

**Click any point in New York City — or search an address — and see every civic district that contains it, and who represents you there.**

A single-file, dependency-light web app: one `index.html`, Leaflet for the map, no build step, no framework, no server-side code. Deployed as a static site — any static host or server works.

> **Status: all 24 layers live with officeholders; roster pipeline proven end-to-end.** This is the New York City fork of [District Explorer](https://github.com/ThursdaysFamous/DistrictExplorer-CHI) (Chicago is the reference implementation), built thread by thread following [`METRO_EXPANSION_PLAYBOOK.md`](METRO_EXPANSION_PLAYBOOK.md). **All build threads (0–6) are complete** — the full **24-layer** civic profile is wired (**Geography**: Borough/County, NTA, ZIP; **Political**: City Council, Election District, Community District/Board, U.S. House, NY Senate & Assembly, Judicial & Civil Court, Borough President, District Attorney; **Public Safety**: NYPD Precinct + Sector, Police Station & Firehouse, FDNY Battalion; **Schools**: ES/MS/HS zones with honest choice-based empty states, Community School District, CEC, School sites). The **roster pipeline** names the officeholders — NY Senate & Assembly (Open Legislation API), City Council, NYPD precinct commanders, U.S. House, live Community-Board chairs — and has completed its first live cycle: each weekly workflow re-scrapes its roster and opens a PR for human review (the first, [PR #6](https://github.com/ThursdaysFamous/DistrictExplorer-NYC/pull/6), refreshed the state legislature and populated every member's district-office address via Open States). Political cards now carry office addresses with card + map pins wherever a verified source exists, and the Thread 6 audit made the z-order and service-worker cache-list invariants executable in the static gate. Community Education Council members and Borough President / District Attorney names are the only rosters still pending (a Playwright scrape and operator-verified input, respectively).

## Running it

There is nothing to build.

```bash
# any static server works:
python3 -m http.server 8000
# then open http://localhost:8000/
```

## What it answers (24 NYC layers)

Pick a point. The app runs a point-in-district lookup across every layer you have toggled on and builds a "civic profile" for that location. The NYC roster is **24 layers** (`METRO_EXPANSION_PLAYBOOK.md` §7):

| Group | Layers |
|---|---|
| **Political** (10) | City Council District · Election District · Community District / Community Board · U.S. House District · NY State Senate · NY State Assembly · NY Supreme Court Judicial District · Civil Court (Municipal Court) District · Borough President · District Attorney |
| **Public Safety** (5) | NYPD Precinct · NYPD Sector · Police Station (nearest 3) · Firehouse (nearest 3) · FDNY Battalion |
| **Schools** (6) | Elementary / Middle / High School Zone · Community School District · Community Education Council · School (nearest 3) |
| **Geography** (3) | Neighborhood (NTA) · ZIP Code (MODZCTA) · Borough / County |

Every result card is independent: a layer whose data source is down shows an error with a Retry button in that card and never affects the others. Because NYC is water-heavy, many in-bounds clicks land in rivers or bays and honestly resolve to **no district** — the app never snaps to the nearest.

Chicago layers with no honest NYC analog (county legislature, elected school board, elected police-oversight board, elected property-tax board) are **dropped, not faked** — see the playbook.

### Shareable links

The URL hash mirrors your current view (`#point=40.71274,-74.00602&layers=borough,council`). Copy it from the URL bar — or use the **Copy link** button on the selected-point chip — and anyone opening the link sees the same point with the same layers on.

## Architecture

Stable core + pluggable layer modules, all inside `index.html`. The engine contract and build history live in [`docs/BUILD_PLAYBOOK_1.md`](docs/BUILD_PLAYBOOK_1.md); the NYC port plan lives in [`METRO_EXPANSION_PLAYBOOK.md`](METRO_EXPANSION_PLAYBOOK.md).

- **Core (metro-agnostic, ~60–65% of `index.html`)**: Leaflet map, click-to-select + GeoSearch geocoder (debounced, NYC-scoped), global `{selectedPoint, sequence}` state where a monotonic sequence counter discards stale async results, shared `sanitize` / `pointInGeometry` / `fetchJSONWithRetry` utilities, the four layer factories (`registerPolygonLayer` / `registerSchoolZone` / `registerCpsNetwork` / `registerIlgaChamber`) and the Socrata / ArcGIS / TIGERweb loaders, layer registry + result-card framework with per-layer failure isolation, selected-boundary highlight, URL-hash permalinks.
- **Modules**: each layer registers `{id, group, label, overlay:{load, style}, query(point, seq), render(result)}`. Overlays lazy-load on first toggle and are cached; `query` runs a local point-in-polygon test against the cached boundaries (or nearest-N haversine for point layers).
- **Honesty rules**: external strings are sanitized or rendered via `textContent`; officeholder data is never guessed — where no verifiable roster source exists, cards link to the official body instead.

### Data sources (NYC)

| Source | Used for |
|---|---|
| [NYC Open Data](https://opendata.cityofnewyork.us) (Socrata) | Council, community & election districts, precincts/sectors, firehouses, school zones/districts, NTAs, ZIP (MODZCTA), community-board leadership |
| NYC Planning ArcGIS (`services5.arcgis.com/GfwWNkhOj9bNBqoJ`) | Election districts, FDNY battalions |
| NYSED ArcGIS (`services6.arcgis.com/EbVsqZ18sv1kVJ3k`) | School points (public / charter / private) |
| [U.S. Census TIGERweb](https://tigerweb.geo.census.gov) | U.S. House, NY Senate, NY Assembly boundaries; judicial/municipal county geometry |
| [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) | U.S. House roster (NY reps) |
| NY Open Legislation API · [Open States](https://openstates.org) (district offices) | NY Senate & Assembly roster + office addresses (weekly CI) |
| council.nyc.gov · nyc.gov precinct pages · schools.nyc.gov (CI scrapers) | City Council roster + district offices, NYPD precinct commanders, CEC members |
| [NYC Planning GeoSearch](https://geosearch.planninglabs.nyc) (Pelias, keyless, PAD-backed) | Address search + address pins |

## Repository layout

```
index.html                   the entire app (styles, engine, layer modules)
METRO_EXPANSION_PLAYBOOK.md   the metro-porting recipe (Part I) + NYC worked example & build log (Part II)
scripts/smoke_test.mjs        Playwright boot/behaviour smoke test (runs on every PR)
scripts/validate_index.py     static gate: layer ids + z-order rank, sw.js cache lists, anchor counts, roster floors
scripts/build_embedded_boundaries.py  simplifies source GeoJSON into data/app/*.json (the 3 offline anchors)
scripts/*.py                  NYC scraper/builder pairs (state legislature, council, NYPD, CEC, congress)
.github/workflows/            per-PR smoke test · deploy · five weekly roster crons (each opens a PR for review)
docs/BUILD_PLAYBOOK_1.md      engine architecture contract + Chicago build/status log
docs/OPTIMIZATION_PLAYBOOK.md optimization & refinement playbook
```

> **Operator setup still pending** (playbook §11): confirm the `SOCRATA_APP_TOKEN` repo secret for CI (the app-side token is already wired in `index.html`), replace the placeholder PWA icons in `icons/app/`, and supply the initial `borough-officials.json` (5 Borough Presidents + 5 District Attorneys, hand-verified — officeholders are never guessed).

## Not for legal or official use

Boundary and roster data come from public sources that explicitly disclaim legal precision. Always confirm district assignments and officeholders with the relevant government office before relying on them for anything official.
