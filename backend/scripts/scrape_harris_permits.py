"""Pull issued permits from unincorporated Harris County (HCPID).

Source: the public HCPID "Issued Permits" ArcGIS FeatureServer — no token,
~1.19M permits, point geometry. This covers unincorporated Harris County
(NW 290 corridor, Generation Park, Channelview) where the largest warehouse
/ distribution boxes are built — the gap City-of-Houston data can't see.

Field reality vs. our COH data (see to_harris_row): Harris exposes permit no,
project name, address, type, issue date, status, and location — but NO
valuation, NO square footage, NO builder, and NO free-text description. So
warehouse VALUE / SIZE / use_class refinement happens later via the HCAD
appraisal match (enrich_from_hcad.py). PROJECTNAME is mapped to `comments`
because it sometimes carries a useful hint ("... LOGISTICS PARK").

Run from `backend/`:
    python -m scripts.scrape_harris_permits --since 2023-01-01            # dry-run
    python -m scripts.scrape_harris_permits --since 2023-01-01 --apply
    python -m scripts.scrape_harris_permits --where "FULLADDRESS LIKE '%CHANNELVIEW%'" --apply
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.dialects.sqlite import insert as sqlite_insert  # noqa: E402

from db import engine, Base  # noqa: E402
from models import Permit  # noqa: E402
from scripts.classify_use_class import classify  # noqa: E402

LAYER = (
    "https://www.gis.hctx.net/arcgishcpid/rest/services/Permits/"
    "IssuedPermits/FeatureServer/0/query"
)
OUT_FIELDS = [
    "PROJECTNUMBER", "PROJECTNAME", "FULLADDRESS", "APPTYPE",
    "PERMITNUMBER", "PERMITNAME", "PERMITCLASSCODE", "ISSUEDDATE", "STATUS",
]
PAGE = 2000
SOURCE = "harris_county"

# Default: new commercial *building* construction since the cutoff. Tenant
# improvements / driveways / OSSFs are excluded — they're not new boxes.
# Override entirely with --where for ad-hoc pulls.
DEFAULT_TYPE_CLAUSE = (
    "(APPTYPE LIKE '%Commercial Building%' OR PERMITNAME LIKE '%Commercial Building%' "
    "OR APPTYPE LIKE '%Site Development%')"
)

ZIP_RE = re.compile(r"\b(\d{5})\b(?:-\d{4})?\s*$")


def epoch_ms_to_date(ms) -> date | None:
    if ms is None:
        return None
    try:
        return datetime.utcfromtimestamp(int(ms) / 1000).date()
    except (ValueError, OSError, TypeError):
        return None


def to_harris_row(attrs: dict, geom: dict | None) -> dict | None:
    """Map one ArcGIS feature to our Permit columns. Returns None if it lacks
    the minimum identity (project number) we need to dedupe on."""
    pn = (attrs.get("PROJECTNUMBER") or "").strip()
    if not pn:
        return None

    permit_no = (attrs.get("PERMITNUMBER") or "").strip()
    # Strip the redundant "<project>-" prefix for a clean sub-permit code;
    # fall back to the full permit number, then UNK, so the composite unique
    # constraint (project_no, permit_code) always dedupes.
    if permit_no.startswith(pn + "-"):
        permit_code = permit_no[len(pn) + 1:] or permit_no
    else:
        permit_code = permit_no or "UNK"

    full_addr = (attrs.get("FULLADDRESS") or "").strip()
    zip_match = ZIP_RE.search(full_addr)
    zip_code = zip_match.group(1) if zip_match else None
    address = ZIP_RE.sub("", full_addr).rstrip(" ,") if zip_match else full_addr

    project_name = (attrs.get("PROJECTNAME") or "").strip() or None

    lat = lon = None
    if geom:
        lon, lat = geom.get("x"), geom.get("y")  # outSR=4326 → x=lon, y=lat

    return {
        "project_no": pn,
        "permit_code": permit_code,
        "permit_date": epoch_ms_to_date(attrs.get("ISSUEDDATE")),
        "permit_type": (attrs.get("PERMITNAME") or attrs.get("APPTYPE") or "").strip() or None,
        "address": address or None,
        "zip_code": zip_code,
        "comments": project_name,  # no real description in this source; PROJECTNAME is the best hint
        "builder": None,           # not exposed by Harris — filled by appraisal match
        "project_value": None,     # not exposed — filled by appraisal match
        "square_feet": None,       # not exposed — filled by appraisal match
        "use_class": classify(project_name),  # coarse; refined by appraisal match
        "latitude": lat,
        "longitude": lon,
        "source": SOURCE,
    }


def upsert_rows(rows: list[dict]) -> int:
    if not rows:
        return 0
    is_sqlite = engine.dialect.name == "sqlite"
    ins = sqlite_insert if is_sqlite else pg_insert
    with engine.begin() as conn:
        # de-dupe within the batch first (same project_no+permit_code can recur)
        seen, batch = set(), []
        for r in rows:
            key = (r["project_no"], r["permit_code"])
            if key in seen:
                continue
            seen.add(key)
            batch.append(r)
        stmt = ins(Permit).values(batch).on_conflict_do_nothing(
            index_elements=["project_no", "permit_code"]
        )
        conn.execute(stmt)
    return len(rows)


def build_where(args) -> str:
    if args.where:
        return args.where
    clauses = [DEFAULT_TYPE_CLAUSE]
    if args.since:
        clauses.append(f"ISSUEDDATE >= DATE '{args.since}'")
    return " AND ".join(clauses)


def fetch_page(where: str, offset: int) -> dict:
    params = {
        "where": where,
        "outFields": ",".join(OUT_FIELDS),
        "returnGeometry": "true",
        "outSR": "4326",
        "orderByFields": "OBJECTID",
        "resultOffset": offset,
        "resultRecordCount": PAGE,
        "f": "json",
    }
    resp = requests.get(LAYER, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Write to DB (default dry-run)")
    p.add_argument("--since", default="2023-01-01", help="Only ISSUEDDATE >= this (YYYY-MM-DD)")
    p.add_argument("--where", default=None, help="Full WHERE override (ignores --since type filter)")
    p.add_argument("--max-pages", type=int, default=0, help="Cap pages (0 = all) — use for testing")
    p.add_argument("--mark-warehouse", action="store_true",
                   help="Force use_class='warehouse' on all pulled rows. Use ONLY with a "
                        "WHERE that explicitly targets warehouse/distribution project names.")
    args = p.parse_args()

    where = build_where(args)
    print(f"Source: {SOURCE}")
    print(f"WHERE:  {where}")

    # Quick count so we know the scope before pulling.
    count_resp = requests.get(
        LAYER, params={"where": where, "returnCountOnly": "true", "f": "json"}, timeout=60
    ).json()
    print(f"Matching permits: {count_resp.get('count')}")

    offset, page_no, mapped, inserted = 0, 0, 0, 0
    use_class_hits = 0
    samples = []
    while True:
        data = fetch_page(where, offset)
        feats = data.get("features", [])
        if not feats:
            break
        page_no += 1
        rows = []
        for f in feats:
            row = to_harris_row(f.get("attributes", {}), f.get("geometry"))
            if row:
                if args.mark_warehouse:
                    row["use_class"] = "warehouse"
                rows.append(row)
                if row["use_class"]:
                    use_class_hits += 1
                if len(samples) < 4:
                    samples.append(row)
        mapped += len(rows)
        if args.apply:
            inserted += upsert_rows(rows)
        offset += len(feats)
        print(f"  page {page_no}: +{len(feats)} (offset {offset}, mapped {mapped})")
        if not data.get("exceededTransferLimit") and len(feats) < PAGE:
            break
        if args.max_pages and page_no >= args.max_pages:
            print(f"  (stopped at --max-pages {args.max_pages})")
            break
        time.sleep(0.3)  # be polite to the county server

    print(f"\nMapped rows: {mapped}  |  pre-classified use_class on {use_class_hits}")
    print("Sample mapped rows:")
    for s in samples:
        print(f"  {s['project_no']} {s['permit_code']:<14} {str(s['permit_date']):<11} "
              f"{(s['use_class'] or '-'):<11} {s['zip_code']} {(s['address'] or '')[:40]}  | {s['comments']}")
    if not args.apply:
        print("\nDry-run. Re-run with --apply to write.")
    else:
        print(f"\nApplied (upserted, conflicts skipped): {mapped} rows from {SOURCE}.")


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    main()
