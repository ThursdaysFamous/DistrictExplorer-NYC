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
import re
import sys
import time
import urllib.error
import urllib.request

API = "https://legislation.nysenate.gov/api/3/members/{year}?full=true&limit=1000&key={key}"
DEFAULT_OUT = os.path.join(os.path.dirname(__file__), ".cache", "ny_legislature_raw.json")


def _office_lines(office):
    """Card-ready address lines for one Open States office: the ;-split street
    address, then the phone and fax when present. [] when there's no address
    (a phone with no address is not a mappable office — never a guessed one)."""
    if not office or not office.get("address"):
        return []
    lines = [p.strip() for p in re.split(r"[;\n]+", office["address"]) if p.strip()]
    if not lines:
        return []
    if office.get("voice"):
        lines.append("Phone: " + office["voice"])
    if office.get("fax"):
        lines.append("Fax: " + office["fax"])
    return lines


def person_offices(person):
    """{'districtOffice'?: [...], 'capitolOffice'?: [...]} for one Open States
    person — each key present only when that office has an address. The two feed
    the card's "District Office" and "Albany Office" blocks respectively. A record
    that labels neither is treated as district-only (the local, on-map office) so
    the common case still shows a pin; a person with no addressed office maps to {}.
    """
    offs = person.get("offices") or []
    district = next((o for o in offs if o.get("classification") == "district" and o.get("address")), None)
    capitol = next((o for o in offs if o.get("classification") == "capitol" and o.get("address")), None)
    if district is None and capitol is None:
        district = next((o for o in offs if o.get("address")), None)
    result = {}
    dlines = _office_lines(district)
    if dlines:
        result["districtOffice"] = dlines
    clines = _office_lines(capitol)
    if clines:
        result["capitolOffice"] = clines
    return result


def openstates_offices():
    """{(CHAMBER, district:int): {'districtOffice'?, 'capitolOffice'?}} from the
    Open States v3 API (`include=offices`, keyed by `current_role.district`).
    Returns {} if OPENSTATES_API_KEY is unset or anything goes wrong — the caller
    then ships names-only (an address is never guessed).
    """
    key = os.environ.get("OPENSTATES_API_KEY")
    if not key:
        return {}
    out = {}
    CH = {"upper": "SENATE", "lower": "ASSEMBLY"}
    try:
        for org, chamber in CH.items():
            page = 1
            while page <= 10:  # NY: senate ~2 pp, assembly ~3 pp at per_page=50
                url = ("https://v3.openstates.org/people?jurisdiction=New%20York"
                       "&org_classification=" + org + "&include=offices&per_page=50&page=" + str(page))
                req = urllib.request.Request(url, headers={"X-API-KEY": key, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    payload = json.load(r)
                for person in payload.get("results", []):
                    role = person.get("current_role") or {}
                    d = role.get("district")
                    if d is None:
                        continue
                    try:
                        dnum = int(str(d).strip())
                    except ValueError:
                        continue
                    offices = person_offices(person)
                    if offices:
                        out[(chamber, dnum)] = offices
                pag = payload.get("pagination") or {}
                if page >= (pag.get("max_page") or page):
                    break
                page += 1
                time.sleep(6)  # Open States free tier is rate-limited (~10/min)
    except Exception as e:  # noqa: BLE001 — enrichment is best-effort, never fatal
        print("Open States office enrichment skipped: %s" % e, file=sys.stderr)
        return {}
    n_d = sum(1 for v in out.values() if v.get("districtOffice"))
    n_c = sum(1 for v in out.values() if v.get("capitolOffice"))
    print("Open States: %d district + %d Albany offices across %d districts" % (n_d, n_c, len(out)), file=sys.stderr)
    return out


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

    # Optional district + Albany office enrichment from the Open States v3 API
    # (structured offices; nysenate.gov WAF-blocks automated requests, so it is
    # not a viable CI source). Needs a free OPENSTATES_API_KEY (§11); absent or on
    # any error we ship names-only, never guessing an address.
    offices = openstates_offices()

    records = []
    for m in items:
        person = m.get("person") or {}
        chamber = m.get("chamber")
        district = m.get("districtCode")
        rec = {
            "chamber": chamber,                     # "SENATE" | "ASSEMBLY"
            "district": district,
            "name": m.get("fullName") or person.get("fullName"),
            "incumbent": bool(m.get("incumbent")),
            "party": None,                          # not exposed by this endpoint — never guessed
            "source_url": source_url,
            "scraped_at": scraped_at,
        }
        office = offices.get((chamber, int(district))) if district is not None else None
        if office:
            if office.get("districtOffice"):
                rec["districtOffice"] = office["districtOffice"]
            if office.get("capitolOffice"):
                rec["capitolOffice"] = office["capitolOffice"]
        records.append(rec)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"session_year": year, "members": records}, f, indent=2, ensure_ascii=False)
    n_sen = sum(1 for r in records if r["chamber"] == "SENATE")
    n_asm = sum(1 for r in records if r["chamber"] == "ASSEMBLY")
    print("wrote %s: %d members (%d senate, %d assembly)" % (out_path, len(records), n_sen, n_asm), file=sys.stderr)


if __name__ == "__main__":
    main()
