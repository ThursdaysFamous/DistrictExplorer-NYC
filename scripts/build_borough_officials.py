#!/usr/bin/env python3
"""
Build data/app/borough-officials.json (Borough President + District Attorney)
from the operator-maintained scripts/borough_officials_source.json
(METRO_EXPANSION_PLAYBOOK §9, §11.3).

There is no clean machine-readable roster for these 10 offices, and they change
only every 4 years, so — unlike the scraped rosters — this is an operator step:
edit the source JSON with hand-verified names + official URLs, then run this.
Only entries with a non-null name are emitted (a null name -> the card links to
the NYC Green Book and names no one). Officeholder data is never guessed.

Output shape: { "<Borough>": { "bp": {"name","url"}, "da": {"name","url"} } }.

Usage:
    python3 scripts/build_borough_officials.py
"""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(os.path.dirname(__file__), "borough_officials_source.json")
OUT = os.path.join(REPO, "data", "app", "borough-officials.json")
BOROUGHS = ["Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"]


def clean(entry):
    if not entry:
        return None
    name = (entry.get("name") or "").strip()
    if not name:
        return None
    out = {"name": name}
    url = (entry.get("url") or "").strip()
    if url:
        out["url"] = url
    return out


def main():
    src = json.load(open(SRC)).get("boroughs", {})
    roster = {}
    filled = 0
    for boro in BOROUGHS:
        row = src.get(boro, {})
        entry = {}
        for role in ("bp", "da"):
            person = clean(row.get(role))
            if person:
                entry[role] = person
                filled += 1
        if entry:
            roster[boro] = entry

    with open(OUT, "w") as f:
        json.dump(roster, f, indent=0, ensure_ascii=False)
    if filled == 0:
        print("wrote data/app/borough-officials.json: EMPTY — no names filled in the source yet "
              "(operator step §11.3; cards link to the NYC Green Book until then).", file=sys.stderr)
    else:
        print("wrote data/app/borough-officials.json: %d of 10 offices filled" % filled, file=sys.stderr)


if __name__ == "__main__":
    main()
