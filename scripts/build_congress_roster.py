#!/usr/bin/env python3
"""
Build data/app/congress-roster.json — the current NY U.S. House delegation —
from the public @unitedstates/congress-legislators dataset (CC0). No scrape and
no key; the whole state is kept because the TIGERweb congressional geometry the
app joins on is whole-state too (METRO_EXPANSION_PLAYBOOK §9; re-parameterized
from Chicago's IL builder — "IL"->"NY", 17->26 reps).

Output shape: { "<district>": {"name", "party", "url"} }, keyed by district
number. REFUSES to write below the count floor.

Usage:
    python3 scripts/build_congress_roster.py
"""

import json
import os
import sys
import urllib.request

SRC = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "app", "congress-roster.json")
STATE = "NY"
MIN_REPS = 24  # NY has 26 U.S. House seats; tolerate a couple of vacancies


def main():
    data = json.load(urllib.request.urlopen(SRC, timeout=90))
    roster = {}
    for p in data:
        terms = p.get("terms") or []
        if not terms:
            continue
        term = terms[-1]
        if term.get("type") != "rep" or term.get("state") != STATE:
            continue
        name = p["name"].get("official_full") or (p["name"].get("first", "") + " " + p["name"].get("last", "")).strip()
        roster[str(term.get("district"))] = {
            "name": name,
            "party": term.get("party"),
            "url": term.get("url") or "https://www.house.gov/representatives",
        }

    if len(roster) < MIN_REPS:
        print("REFUSING to write congress-roster.json: %d reps < floor %d" % (len(roster), MIN_REPS), file=sys.stderr)
        sys.exit(1)

    roster = {k: roster[k] for k in sorted(roster, key=lambda x: int(x))}
    with open(OUT, "w") as f:
        json.dump(roster, f, indent=0, ensure_ascii=False)
    print("wrote data/app/congress-roster.json: %d NY U.S. House reps" % len(roster), file=sys.stderr)


if __name__ == "__main__":
    main()
