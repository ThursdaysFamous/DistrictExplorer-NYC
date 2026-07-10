#!/usr/bin/env python3
"""
Resolve the council scrape (council_scraper.py) into
data/app/council-members.json  { "<district>": {"name"} }.

Stage 2 of the pipeline (METRO_EXPANSION_PLAYBOOK §9). REFUSES to write below the
count floor so a partial scrape can't overwrite a good roster. Party is not taken
(council.nyc.gov doesn't label it in the district cards) — never guessed.

Usage:
    python3 scripts/build_council_roster.py [--in PATH]
"""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(REPO, "data", "app")
DEFAULT_IN = os.path.join(os.path.dirname(__file__), ".cache", "council_raw.json")
OUT = os.path.join(APP, "council-members.json")
MIN_MEMBERS = 48  # 51 seats; tolerate a few vacancies


def main():
    argv = sys.argv[1:]
    in_path = argv[argv.index("--in") + 1] if "--in" in argv else DEFAULT_IN
    if not os.path.exists(in_path):
        print("no scrape input at %s (run council_scraper.py first)" % in_path, file=sys.stderr)
        sys.exit(2)

    raw = json.load(open(in_path)).get("members", {})
    roster = {}
    for district, rec in raw.items():
        name = (rec.get("name") or "").strip()
        if name:
            entry = {"name": name}
            office = (rec.get("office") or "").strip()
            if office:
                entry["office"] = office
            roster[str(int(district))] = entry

    if len(roster) < MIN_MEMBERS:
        print("REFUSING to write council-members.json: %d members < floor %d" % (len(roster), MIN_MEMBERS), file=sys.stderr)
        sys.exit(1)

    roster = {k: roster[k] for k in sorted(roster, key=lambda x: int(x))}
    with open(OUT, "w") as f:
        json.dump(roster, f, indent=0, ensure_ascii=False)
    print("wrote data/app/council-members.json: %d members" % len(roster), file=sys.stderr)


if __name__ == "__main__":
    main()
