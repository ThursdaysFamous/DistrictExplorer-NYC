#!/usr/bin/env python3
"""
Scrape the 51 NYC City Council members from council.nyc.gov/districts/
(METRO_EXPANSION_PLAYBOOK §9). Stage 1 of the pipeline.

Note on source: the playbook named Legistar's People.aspx, but its "Web Site"
column (the only place the district number appears) is populated for only ~24 of
51 members. council.nyc.gov/districts/ lists all 51 with the member name in each
district card's photo alt text and the district number in the card's URL, so it
is the complete, reliable source. Writes an intermediate JSON with source_url +
scraped_at; build_council_roster.py resolves it into data/app/council-members.json.

Usage:
    python3 scripts/council_scraper.py [--out PATH]
"""

import json
import os
import re
import sys
import time
import urllib.request

URL = "https://council.nyc.gov/districts/"
UA = "Mozilla/5.0 (compatible; NYCDistrictExplorer/1.0; +https://nyc.chidistricts.com)"
DEFAULT_OUT = os.path.join(os.path.dirname(__file__), ".cache", "council_raw.json")


def clean_name(alt):
    # photo alts read "Christopher Marte Head Shot" / "... Headshot" / "... Photo"
    name = re.sub(r"\s*(head\s*shot|headshot|photo|portrait)\s*$", "", alt, flags=re.I).strip()
    return name or None


def parse(html):
    parts = re.split(r'href="https://council\.nyc\.gov/district-(\d+)/"', html)
    roster = {}
    for i in range(1, len(parts) - 1, 2):
        num = str(int(parts[i]))
        seg = parts[i + 1][:1500]
        name = None
        for alt in re.findall(r'alt="([^"]+)"', seg):
            alt = alt.strip()
            if alt and not re.search(r"email|phone|address|logo|icon|seal", alt, re.I):
                name = clean_name(alt)
                if name:
                    break
        if name and num not in roster:
            roster[num] = name
    return roster


def main():
    argv = sys.argv[1:]
    out_path = argv[argv.index("--out") + 1] if "--out" in argv else DEFAULT_OUT

    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    roster = parse(html)
    scraped_at = os.environ.get("SCRAPED_AT") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    records = {}
    for district, name in roster.items():
        records[district] = {
            "name": name,
            "source_url": "https://council.nyc.gov/district-%s/" % district,
            "scraped_at": scraped_at,
        }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"members": records}, f, indent=2, ensure_ascii=False)
    print("wrote %s: %d council members" % (out_path, len(records)), file=sys.stderr)


if __name__ == "__main__":
    main()
