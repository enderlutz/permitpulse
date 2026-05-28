"""Backfill permit_date for sold_permits rows with permit_code = 'LEGACY'.

These rows came out of the composite-key migration (migrate_composite_key.py)
which assigned 'LEGACY' to any pre-migration row without a real permit_code.
backfill_dates.py skips them because we don't know which sub-permit to drill.
This script probes the same PT list as enrich_ereport.py until one returns
a Project Details page, then UPDATEs permit_date plus any NULL builder /
project_value.

Run from `backend/`:
    python -m scripts.backfill_legacy_dates --concurrency 5
    python -m scripts.backfill_legacy_dates --limit 200
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import engine  # noqa: E402
from services.sold_permits_scraper import fetch_project_detail  # noqa: E402


PT_PROBE_ORDER = ["PX", "13", "BU", "11", "12", "14", "CC", "BX", "GI", "CO", "S9", "FF", "WK", "WT", "GP"]


def fetch_targets(limit: int | None = None, since_id: int | None = None) -> list[tuple[int, str]]:
    sql = """
        SELECT id, project_no
        FROM permits
        WHERE source = 'houston_sold_permits'
          AND permit_code = 'LEGACY'
          AND project_no IS NOT NULL
    """
    if since_id is not None:
        sql += " AND id > :since_id"
    sql += " ORDER BY id"
    if limit:
        sql += " LIMIT :limit"
    with engine.connect() as c:
        params: dict = {}
        if since_id is not None:
            params["since_id"] = since_id
        if limit:
            params["limit"] = limit
        return [tuple(r) for r in c.execute(text(sql), params)]


def apply_update(row_id: int, detail: dict) -> None:
    set_clauses = ["permit_date = :permit_date"]
    params: dict = {"id": row_id, "permit_date": detail["permit_date"]}
    if detail.get("owner"):
        set_clauses.append("builder = COALESCE(builder, :builder)")
        params["builder"] = detail["owner"]
    if detail.get("project_value") is not None:
        set_clauses.append("project_value = COALESCE(project_value, :project_value)")
        params["project_value"] = detail["project_value"]
    stmt = text(f"UPDATE permits SET {', '.join(set_clauses)} WHERE id = :id")
    with engine.begin() as conn:
        conn.execute(stmt, params)


async def probe_project(client: httpx.AsyncClient, pn: str) -> dict | None:
    for pt in PT_PROBE_ORDER:
        try:
            d = await fetch_project_detail(client, pn, pt)
        except Exception:
            continue
        if d and d.get("permit_date"):
            return d
    return None


async def worker(name: str, queue: asyncio.Queue, results: dict, client: httpx.AsyncClient):
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            return
        row_id, pn = item
        try:
            detail = await asyncio.wait_for(probe_project(client, pn), timeout=60)
            if detail:
                apply_update(row_id, detail)
                results["updated"] += 1
                if results["updated"] % 100 == 0:
                    rate = results["updated"] / max(1, time.time() - results["t0"])
                    eta_m = (results["total"] - results["processed"]) / max(rate, 0.01) / 60
                    print(f"  [{name}] updated {results['updated']}/{results['total']} "
                          f"({rate:.1f}/s, eta {eta_m:.1f}m)")
            else:
                results["unmatched"] += 1
        except asyncio.TimeoutError:
            results["timeouts"] += 1
        except Exception as e:
            results["errors"] += 1
            if results["errors"] <= 10:
                print(f"  [{name}] ✗ id={row_id} pn={pn}: {type(e).__name__}: {e}")
        finally:
            results["processed"] += 1
            queue.task_done()


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--limit", type=int)
    p.add_argument("--since-id", type=int)
    args = p.parse_args()

    print("Fetching LEGACY-coded sold_permits rows...")
    targets = fetch_targets(limit=args.limit, since_id=args.since_id)
    if not targets:
        print("Nothing to backfill.")
        return
    print(f"  {len(targets)} rows (concurrency={args.concurrency})")
    print(f"  First: id={targets[0][0]} pn={targets[0][1]}")
    print(f"  Last:  id={targets[-1][0]} pn={targets[-1][1]}")

    queue: asyncio.Queue = asyncio.Queue()
    for t in targets:
        await queue.put(t)
    for _ in range(args.concurrency):
        await queue.put(None)

    results = {"processed": 0, "updated": 0, "unmatched": 0, "errors": 0,
               "timeouts": 0, "total": len(targets), "t0": time.time()}

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        workers = [asyncio.create_task(worker(f"W{i}", queue, results, client))
                   for i in range(args.concurrency)]
        await queue.join()
        for w in workers:
            await w

    elapsed = time.time() - results["t0"]
    print()
    print("=" * 60)
    print(f"  total      : {results['total']}")
    print(f"  updated    : {results['updated']}")
    print(f"  unmatched  : {results['unmatched']}")
    print(f"  errors     : {results['errors']}")
    print(f"  timeouts   : {results['timeouts']}")
    print(f"  elapsed    : {elapsed:.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
