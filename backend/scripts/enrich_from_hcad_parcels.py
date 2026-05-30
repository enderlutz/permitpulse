"""Enrich Harris County permits with HCAD parcel data (owner + market value).

The HCAD bulk-download feed is currently broken/gated, so we use the public
HCAD Parcels ArcGIS layer (same server as the permits layer) instead. It
exposes per-parcel owner_name, state_class, building value, and market value.

It does NOT expose building square footage or a clean warehouse flag, and
appraisal data LAGS construction — a brand-new warehouse still shows its old
parcel use. To avoid attaching stale/misleading data, we ONLY enrich a permit
when the matched parcel is an established commercial/industrial building:
    state_class IN ('F1','F2')  AND  bld_value > 0
That guardrail skips the freshness-lag mismatches (e.g. a logistics permit
whose parcel still appraises as a J4 telecom site).

We fill builder and project_value only where they are currently NULL — never
overwrite real scraped values.

Run from `backend/`:
    python -m scripts.enrich_from_hcad_parcels                 # dry-run, all harris_county
    python -m scripts.enrich_from_hcad_parcels --apply
    python -m scripts.enrich_from_hcad_parcels --warehouse-only --apply
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from db import engine  # noqa: E402

PARCELS = (
    "https://www.gis.hctx.net/arcgis/rest/services/HCAD/Parcels/MapServer/0/query"
)
DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}


def parse_address(addr: str) -> tuple[int, str] | None:
    """Pull (street_number, street_name_prefix) from a permit address like
    '12603 Conklin Ln Houston TX' -> (12603, 'CONKLIN'). Drops a leading
    directional so '3520 E Sam Houston N Pkwy' -> (3520, 'SAM')."""
    if not addr:
        return None
    m = re.match(r"\s*(\d+)\s+(.+)", addr)
    if not m:
        return None
    num = int(m.group(1))
    toks = [t.strip('".,') for t in m.group(2).upper().split() if t.strip('".,')]
    if toks and toks[0] in DIRECTIONALS:
        toks = toks[1:]
    if not toks:
        return None
    return num, toks[0]


def escape_sql(s: str) -> str:
    return s.replace("'", "''")


def lookup_parcel(num: int, name_prefix: str, zip_code: str | None) -> dict | None:
    """Find the established commercial/industrial parcel at this address.
    Returns the best (highest building value) F1/F2 parcel, or None."""
    where = (
        f"site_str_num = {num} "
        f"AND site_str_name LIKE '{escape_sql(name_prefix)}%' "
        f"AND state_class IN ('F1','F2') AND bld_value > 0"
    )
    if zip_code:
        where += f" AND site_zip = '{escape_sql(zip_code)}'"
    params = {
        "where": where,
        "outFields": "owner_name_1,state_class,land_use,bld_value,total_market_val,site_str_name",
        "returnGeometry": "false",
        "f": "json",
    }
    try:
        r = requests.get(PARCELS, params=params, timeout=45)
        r.raise_for_status()
        feats = r.json().get("features", [])
    except Exception as ex:
        print(f"    ! lookup error ({num} {name_prefix}): {ex}")
        return None
    if not feats:
        return None
    feats.sort(key=lambda f: f["attributes"].get("bld_value") or 0, reverse=True)
    return feats[0]["attributes"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Write enrichment (default dry-run)")
    p.add_argument("--warehouse-only", action="store_true",
                   help="Only enrich use_class='warehouse' rows")
    p.add_argument("--source", default="harris_county")
    args = p.parse_args()

    sel = (
        "SELECT id, address, zip_code, builder, project_value, use_class "
        "FROM permits WHERE source = :src "
        "AND (builder IS NULL OR project_value IS NULL)"
    )
    if args.warehouse_only:
        sel += " AND use_class = 'warehouse'"
    with engine.connect() as c:
        rows = c.execute(text(sel), {"src": args.source}).all()
    print(f"Candidates from {args.source}: {len(rows)}")

    matched = filled_builder = filled_value = unmatched = unparsed = 0
    updates = []
    for r in rows:
        parsed = parse_address(r.address or "")
        if not parsed:
            unparsed += 1
            continue
        num, name = parsed
        parcel = lookup_parcel(num, name, r.zip_code)
        time.sleep(0.15)
        if not parcel:
            unmatched += 1
            continue
        matched += 1
        new_builder = (parcel.get("owner_name_1") or "").strip() or None
        new_value = parcel.get("total_market_val")
        upd = {"id": r.id}
        if r.builder is None and new_builder:
            upd["builder"] = new_builder
            filled_builder += 1
        if r.project_value is None and new_value:
            upd["project_value"] = float(new_value)
            filled_value += 1
        if len(upd) > 1:
            updates.append(upd)
            if len(updates) <= 8:
                print(f"  #{r.id} {r.address[:34]:<34} -> {parcel.get('state_class')} "
                      f"${int(new_value or 0):,} | {new_builder}")

    print(f"\nmatched parcels: {matched} | builder fills: {filled_builder} | "
          f"value fills: {filled_value} | unmatched: {unmatched} | unparsed: {unparsed}")

    if not args.apply:
        print("\nDry-run. Re-run with --apply to write.")
        return

    applied = 0
    with engine.begin() as conn:
        for upd in updates:
            sets = ", ".join(f"{k} = :{k}" for k in upd if k != "id")
            conn.execute(text(f"UPDATE permits SET {sets} WHERE id = :id"), upd)
            applied += 1
    print(f"\nApplied enrichment to {applied} rows.")


if __name__ == "__main__":
    main()
