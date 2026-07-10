#!/usr/bin/env python3
"""
Monthly freshness check for the NYC school-zone datasets, whose Socrata dataset
IDs rotate every school year (METRO_EXPANSION_PLAYBOOK §9).

Heuristic (refined in Thread 3): NYC publishes each year's zones as a *new*
dataset named e.g. "School Zones 2024-2025 (Elementary School)" and leaves the
previous ones in place, and the current boundaries can legitimately sit
unchanged for 2+ years — so a plain "rowsUpdatedAt is old" test cries wolf on
perfectly current data. Instead, for each pinned dataset this:
  - flags a 404 (the id was retired), and
  - searches the catalog for the same level and flags when a NEWER school-year
    zones dataset exists than the one we're pinned to (time to swap the id).

Prints a human-readable summary; exits non-zero if any level needs attention so
.github/workflows/check-school-zone-ids.yml can open a tracking issue (never a
PR — the fix is a human swapping the id). Read-only; never edits the app.

Usage:
    python3 scripts/check_school_zone_ids.py
    SOCRATA_APP_TOKEN=... python3 scripts/check_school_zone_ids.py   # optional
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

HOST = "https://data.cityofnewyork.us"

# level -> the dataset id wired into index.html's registerSchoolZone calls.
PINNED = {
    "Elementary": "cmjf-yawu",
    "Middle": "t26j-jbq7",
    "High": "ruu9-egea",
}


def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    token = os.environ.get("SOCRATA_APP_TOKEN")
    if token:
        req.add_header("X-App-Token", token)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _parse(name):
    """('School Zones 2024-2025 (Elementary School)') -> ('Elementary', 2024)."""
    ym = re.search(r"(\d{4})\s*-\s*\d{4}", name or "")
    lm = re.search(r"\((Elementary|Middle|High)\s+School\)", name or "", re.I)
    year = int(ym.group(1)) if ym else None
    level = lm.group(1).title() if lm else None
    return level, year


def _catalog_latest():
    """Newest (start-year, id) per level found in the open-data catalog."""
    best = {}
    try:
        d = _get(HOST + "/api/catalog/v1?q=School%20Zones&only=dataset&limit=50")
    except Exception as e:  # noqa: BLE001
        return best, "catalog search failed: %s" % e
    for r in d.get("results", []):
        res = r.get("resource", {})
        level, year = _parse(res.get("name", ""))
        if level and year and (level not in best or year > best[level][1]):
            best[level] = (res.get("id"), year)
    return best, None


def main():
    problems = []
    latest, err = _catalog_latest()
    if err:
        print("WARN  " + err)

    for level, pid in PINNED.items():
        try:
            meta = _get(HOST + "/api/views/" + pid + ".json")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                problems.append("%s (%s): 404 — dataset id retired/rotated" % (level, pid))
                print("FAIL  %s (%s) — 404, id retired/rotated" % (level, pid))
                continue
            print("WARN  %s (%s) — HTTP %d fetching metadata" % (level, pid, e.code))
            continue
        except Exception as e:  # noqa: BLE001
            print("WARN  %s (%s) — fetch error: %s" % (level, pid, e))
            continue

        _, pinned_year = _parse(meta.get("name", ""))
        newer = latest.get(level)
        if newer and pinned_year and newer[1] > pinned_year:
            problems.append(
                "%s: pinned %s (%d-%d) but catalog has a newer %d-%d dataset %s"
                % (level, pid, pinned_year, pinned_year + 1, newer[1], newer[1] + 1, newer[0])
            )
            print(
                "FAIL  %s (%s) — newer school-year dataset available: %s (%d-%d)"
                % (level, pid, newer[0], newer[1], newer[1] + 1)
            )
        else:
            latest_str = ("%d-%d" % (newer[1], newer[1] + 1)) if newer else "n/a"
            print("PASS  %s (%s) — %s (catalog latest: %s)" % (level, pid, meta.get("name"), latest_str))

    if problems:
        print("\nSchool-zone datasets need attention:")
        for p in problems:
            print("  - " + p)
        print(
            "\nFix: update the rotated id in index.html (es/ms/hs registerSchoolZone) "
            "and in PINNED above. The layers are live, so nothing else re-derives."
        )
        sys.exit(1)
    print("\nAll school-zone datasets are the latest published school year.")


if __name__ == "__main__":
    main()
