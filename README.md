# NYC District Explorer

**Click any point in New York City — or search an address — and see every civic district that contains it, and who represents you there.**

A single-file, dependency-light web app: one `index.html`, Leaflet for the map, no build step, no framework, no server-side code. Deployed as a static site — any static host or server works.

> **Status: porting in progress — all 24 layers live.** This is the New York City fork of [District Explorer](https://github.com/ThursdaysFamous/DistrictExplorer-CHI) (Chicago is the reference implementation), built thread by thread following [`METRO_EXPANSION_PLAYBOOK.md`](METRO_EXPANSION_PLAYBOOK.md). **Threads 0–4 are complete** — the full **24-layer** civic profile is wired: the metro-agnostic engine on an NYC map (keyless [NYC Planning GeoSearch](https://geosearch.planninglabs.nyc) geocoder); **Geography** (Borough/County, NTA, ZIP); **Political** (City Council, Election District, Community District/Board with a live board-chair join, U.S. House with a real roster, NY Senate & Assembly, Judicial & Civil Court, Borough President, District Attorney); **Public Safety** (NYPD Precinct + Sector, Police Station & Firehouse nearest-3, FDNY Battalion); **Schools** (ES/MS/HS zones with honest choice-based empty states, Community School District, CEC, School sites). Remaining work is the **roster pipeline** (Thread 5 — scrapers + weekly CI fill the officeholder names that currently link to the official body) and a final **audit/deploy** pass (Thread 6).

## Running it

There is nothing to build.

```bash
# any static server works:
python3 -m http.server 8000
# then open http://localhost:8000/
```

## What it will answer (planned NYC layers)

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

The URL hash mirrors your current view (`#point=40.71274,-74.00602&layers=stub`). Copy it from the URL bar — or use the **Copy link** button on the selected-point chip — and anyone opening the link sees the same point with the same layers on.

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
| nysenate.gov · nyassembly.gov · Legistar · schools.nyc.gov (scraped by CI) | State legislature, City Council, and CEC rosters |
| [NYC Planning GeoSearch](https://geosearch.planninglabs.nyc) (Pelias, keyless, PAD-backed) | Address search + address pins |

## Repository layout

```
index.html                   the entire app (styles, engine, layer modules)
METRO_EXPANSION_PLAYBOOK.md   the NYC port plan (Part I recipe · Part II NYC worked example)
scripts/smoke_test.mjs        Playwright boot/behaviour smoke test (runs on every PR)
scripts/validate_index.py     post-regeneration static gate (Chicago template — re-derived in Thread 6)
scripts/build_embedded_boundaries.py  simplifies source GeoJSON into data/app/*.json (reused for NYC anchors)
scripts/*.py                  Chicago scraper/builder templates (rewritten for NYC in Thread 5, §9)
.github/workflows/            per-PR smoke test + deploy; Chicago roster crons are templates for Thread 5
docs/BUILD_PLAYBOOK_1.md      engine architecture contract + Chicago build/status log
docs/OPTIMIZATION_PLAYBOOK.md optimization & refinement playbook
```

> **Operator setup still pending** (playbook §11): register a free Socrata app token (set `SOCRATA_APP_TOKEN` in `index.html` + the CI secret), point the custom domain (`CNAME`) and confirm it is owned, replace the placeholder `icons/`, and supply the initial `borough-officials.json`.

## Not for legal or official use

Boundary and roster data come from public sources that explicitly disclaim legal precision. Always confirm district assignments and officeholders with the relevant government office before relying on them for anything official.
