#!/usr/bin/env python3
"""
Scrape the current NY State Senate + Assembly membership from the NY Senate
Open Legislation API (METRO_EXPANSION_PLAYBOOK §9). Stage 1 of the two-stage
pipeline: fetch the raw member list and write an intermediate JSON file with a
`source_url` + `scraped_at` on every record; build_ny_roster.py resolves it into
the two data/app/*.json roster files with count guards.

The API is key-gated (401 without a key). Set NYSENATE_API_KEY (a repo secret in
CI; see §11.6). Party is NOT exposed by the /members endpoint, so it is stored
null and never guessed — the card links to the member's chamber directory where
party is shown.

Usage:
    NYSENATE_API_KEY=... python3 scripts/ny_legislature_scraper.py [--out PATH]
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://legislation.nysenate.gov/api/3/members/{year}?full=true&limit=1000&key={key}"
DEFAULT_OUT = os.path.join(os.path.dirname(__file__), ".cache", "ny_legislature_raw.json")


def main():
    out_path = DEFAULT_OUT
    argv = sys.argv[1:]
    if "--out" in argv:
        out_path = argv[argv.index("--out") + 1]

    key = os.environ.get("NYSENATE_API_KEY")
    if not key:
        print("NYSENATE_API_KEY is not set (Open Legislation API key required).", file=sys.stderr)
        sys.exit(2)
    year = os.environ.get("NY_SESSION_YEAR", "2025")

    try:
        with urllib.request.urlopen(API.format(year=year, key=key), timeout=90) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        print("Open Legislation API HTTP %d (401 = bad/absent key)" % e.code, file=sys.stderr)
        sys.exit(1)
    if not data.get("success"):
        print("Open Legislation API returned success=false", file=sys.stderr)
        sys.exit(1)

    items = data.get("result", {}).get("items", [])
    scraped_at = os.environ.get("SCRAPED_AT") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    source_url = "https://legislation.nysenate.gov/api/3/members/%s" % year

    records = []
    for m in items:
        person = m.get("person") or {}
        records.append({
            "chamber": m.get("chamber"),          # "SENATE" | "ASSEMBLY"
            "district": m.get("districtCode"),
            "name": m.get("fullName") or person.get("fullName"),
            "incumbent": bool(m.get("incumbent")),
            "party": None,                          # not exposed by this endpoint — never guessed
            "source_url": source_url,
            "scraped_at": scraped_at,
        })

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"session_year": year, "members": records}, f, indent=2, ensure_ascii=False)
    n_sen = sum(1 for r in records if r["chamber"] == "SENATE")
    n_asm = sum(1 for r in records if r["chamber"] == "ASSEMBLY")
    print("wrote %s: %d members (%d senate, %d assembly)" % (out_path, len(records), n_sen, n_asm), file=sys.stderr)


if __name__ == "__main__":
    main()
