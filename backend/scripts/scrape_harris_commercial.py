"""Pull ALL Harris County commercial-BUILDING permits (not just warehouses).

Expands coverage from the warehouse-named subset to every commercial new
building permit in unincorporated Harris County. Use class is a best-effort
guess from the project name (classify_use_class); anything the name doesn't
clearly indicate is left as 'general' → shown in the app as
"Unknown/Pending/General classification".

Per the client: name-based use is an ASSUMPTION (the API flags it via
use_class_assumed → the UI shows an asterisk), NOT a confident label. The
permit OWNER is filled from the ePermits/Projects service (PROPERTYOWNERNAME,
no appraisal lag) so the developer can judge use from experience.

Re-runnable: idempotent upsert; safe to schedule. As HCAD appraisal data and
classification improve over time, a scheduled re-run resolves 'general' rows.

Run from `backend/`:
    python -m scripts.scrape_harris_commercial --since 2023-01-01            # dry-run
    python -m scripts.scrape_harris_commercial --since 2023-01-01 --apply
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.scrape_harris_permits import (  # noqa: E402
    LAYER, OUT_FIELDS, PAGE, epoch_ms_to_date, ZIP_RE, upsert_rows,
)
from scripts.classify_use_class import classify  # noqa: E402
from schemas import classify_permit_nature  # noqa: E402

EPERMITS = "https://www.gis.hctx.net/arcgishcpid/rest/services/Permits/ePermits/MapServer/0/query"
SOURCE = "harris_county"

COMMERCIAL_WHERE = "(APPTYPE LIKE '%Commercial Building%' OR PERMITNAME LIKE '%Commercial Building%')"


def fetch_owner_map(project_nos: list[str]) -> dict[str, str]:
    """Look up PROPERTYOWNERNAME per PROJECTNUMBER from ePermits/Projects,
    chunked into IN() queries. Owner comes straight off the permit app — no
    appraisal lag — so it's available even for brand-new builds."""
    owners: dict[str, str] = {}
    CHUNK = 120
    for i in range(0, len(project_nos), CHUNK):
        chunk = project_nos[i:i + CHUNK]
        in_list = ",".join("'" + p.replace("'", "''") + "'" for p in chunk)
        try:
            # POST (not GET) — a 120-id IN() clause overflows the URL length
            # limit and the server 404s. ArcGIS query endpoints accept POST.
            r = requests.post(EPERMITS, data={
                "where": f"PROJECTNUMBER IN ({in_list})",
                "outFields": "PROJECTNUMBER,PROPERTYOWNERNAME",
                "returnGeometry": "false", "f": "json",
            }, timeout=60)
            r.raise_for_status()
            for f in r.json().get("features", []):
                a = f["attributes"]
                pn = (a.get("PROJECTNUMBER") or "").strip()
                own = (a.get("PROPERTYOWNERNAME") or "").strip()
                if pn and own:
                    owners[pn] = own
        except Exception as ex:
            print(f"    ! owner lookup chunk {i} failed: {ex}")
        time.sleep(0.1)
    return owners


def to_row(attrs: dict, geom: dict | None, owner_map: dict[str, str]) -> dict | None:
    pn = (attrs.get("PROJECTNUMBER") or "").strip()
    if not pn:
        return None
    permit_no = (attrs.get("PERMITNUMBER") or "").strip()
    permit_code = permit_no[len(pn) + 1:] if permit_no.startswith(pn + "-") else (permit_no or "UNK")
    full_addr = (attrs.get("FULLADDRESS") or "").strip()
    zm = ZIP_RE.search(full_addr)
    zip_code = zm.group(1) if zm else None
    address = ZIP_RE.sub("", full_addr).rstrip(" ,") if zm else full_addr
    project_name = (attrs.get("PROJECTNAME") or "").strip() or None
    lat = lon = None
    if geom:
        lon, lat = geom.get("x"), geom.get("y")
    # Best-effort use class from the name; 'general' when the name isn't telling.
    use_class = classify(project_name) or "general"
    permit_type = (attrs.get("PERMITNAME") or attrs.get("APPTYPE") or "").strip() or None
    return {
        "project_no": pn,
        "permit_code": permit_code,
        "permit_date": epoch_ms_to_date(attrs.get("ISSUEDDATE")),
        "permit_type": permit_type,
        "permit_nature": classify_permit_nature(permit_type, project_name),
        "address": address or None,
        "zip_code": zip_code,
        "comments": project_name,
        "builder": owner_map.get(pn),  # from ePermits, no appraisal lag
        "project_value": None,
        "square_feet": None,
        "use_class": use_class,
        "latitude": lat,
        "longitude": lon,
        "source": SOURCE,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--since", default="2023-01-01")
    p.add_argument("--max-pages", type=int, default=0)
    args = p.parse_args()

    where = f"{COMMERCIAL_WHERE} AND ISSUEDDATE >= DATE '{args.since}'"
    print(f"Source: {SOURCE}\nWHERE:  {where}")
    cnt = requests.get(LAYER, params={"where": where, "returnCountOnly": "true", "f": "json"}, timeout=60).json()
    print(f"Matching commercial-building permits: {cnt.get('count')}")

    # First pass: collect all features (we need project_nos for owner lookup).
    offset, page_no, feats_all = 0, 0, []
    while True:
        params = {
            "where": where, "outFields": ",".join(OUT_FIELDS), "returnGeometry": "true",
            "outSR": "4326", "orderByFields": "OBJECTID",
            "resultOffset": offset, "resultRecordCount": PAGE, "f": "json",
        }
        data = requests.get(LAYER, params=params, timeout=90).json()
        feats = data.get("features", [])
        if not feats:
            break
        page_no += 1
        feats_all.extend(feats)
        offset += len(feats)
        print(f"  fetched page {page_no} (+{len(feats)}, total {len(feats_all)})")
        if not data.get("exceededTransferLimit") and len(feats) < PAGE:
            break
        if args.max_pages and page_no >= args.max_pages:
            break
        time.sleep(0.3)

    project_nos = sorted({(f["attributes"].get("PROJECTNUMBER") or "").strip()
                          for f in feats_all if f["attributes"].get("PROJECTNUMBER")})
    print(f"Looking up owners for {len(project_nos)} projects from ePermits...")
    owner_map = fetch_owner_map(project_nos)
    print(f"  owners found: {len(owner_map)}")

    from collections import Counter
    rows = []
    for f in feats_all:
        r = to_row(f["attributes"], f.get("geometry"), owner_map)
        if r:
            rows.append(r)
    uc = Counter(r["use_class"] for r in rows)
    with_owner = sum(1 for r in rows if r["builder"])
    print(f"\nMapped {len(rows)} rows | with owner: {with_owner}")
    print("use_class distribution (name-based assumption; 'general' = Unknown/Pending):")
    for k, v in uc.most_common():
        print(f"  {v:>5}  {k}")

    if not args.apply:
        print("\nDry-run. Re-run with --apply to write.")
        return
    upsert_rows(rows)
    print(f"\nApplied (upserted, conflicts skipped): {len(rows)} rows from {SOURCE}.")


if __name__ == "__main__":
    main()
