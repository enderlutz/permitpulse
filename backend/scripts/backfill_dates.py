"""Backfill real permit_date (and builder/value/use_class) on existing
sold_permits rows by hitting the sold_permit_d drill-down for each (PN, PT).

Why this exists: every sold_permits row currently has permit_date = scrape day
(today() was hardcoded in to_permit_row before 2026-05-28). All 36k+ rows are
clustered in May 2026 even though they were actually issued anywhere from Jan
2025 through May 2026. The drill-down detail page is the authoritative source.

Run from `backend/`:
    python -m scripts.backfill_dates --concurrency 5
    python -m scripts.backfill_dates --limit 200      # dry-test with a slice
    python -m scripts.backfill_dates --since-id 12345 # resume from a checkpoint

Reads sold_permits rows from the configured DATABASE_URL (Supabase via env, or
local SQLite fallback). Drills one (PN, PT) per row, UPDATEs the row's
permit_date and fills NULL builder / project_value when the detail has them.
Skips rows where permit_code is 'LEGACY' or 'UNK' — those need a search step
first (see enrich_ereport.py).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import bindparam, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import engine  # noqa: E402
from services.sold_permits_scraper import fetch_project_detail  # noqa: E402


QUERY_TIMEOUT_SECS = 30


def fetch_target_rows(limit: int | None = None, since_id: int | None = None) -> list[tuple[int, str, str]]:
    """Pull (id, project_no, permit_code) for every sold_permits row that
    still needs a real date. We filter on source so eReport rows (which
    already have correct dates) are skipped."""
    sql = """
        SELECT id, project_no, permit_code
        FROM permits
        WHERE source = 'houston_sold_permits'
          AND project_no IS NOT NULL
          AND permit_code IS NOT NULL
          AND permit_code NOT IN ('LEGACY', 'UNK')
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
    """Write the recovered fields back. Only overwrite builder/value when the
    existing column is NULL — preserves any post-ingest enrichment work."""
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


async def worker(name: str, queue: asyncio.Queue, results: dict, client: httpx.AsyncClient):
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            return
        row_id, pn, pt = item
        try:
            try:
                detail = await asyncio.wait_for(
                    fetch_project_detail(client, pn, pt), timeout=QUERY_TIMEOUT_SECS
                )
            except asyncio.TimeoutError:
                results["timeouts"] += 1
                continue
            if detail and detail.get("permit_date"):
                apply_update(row_id, detail)
                results["updated"] += 1
                if results["updated"] % 100 == 0:
                    rate = results["updated"] / max(1, time.time() - results["t0"])
                    print(f"  [{name}] updated {results['updated']}/{results['total']}  "
                          f"({rate:.1f}/s, eta {(results['total'] - results['updated']) / max(rate, 0.01) / 60:.1f}m)")
            else:
                results["misses"] += 1
        except Exception as e:
            results["errors"] += 1
            if results["errors"] <= 10:
                print(f"  [{name}] ✗ id={row_id} pn={pn} pt={pt}: {type(e).__name__}: {e}")
        finally:
            queue.task_done()


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--concurrency", type=int, default=5,
                   help="Parallel drill-down requests (default 5, be polite)")
    p.add_argument("--limit", type=int, help="Process only N rows (smoke test)")
    p.add_argument("--since-id", type=int, help="Resume from a permits.id checkpoint")
    args = p.parse_args()

    print("Fetching backfill targets from database...")
    targets = fetch_target_rows(limit=args.limit, since_id=args.since_id)
    if not targets:
        print("No rows need backfill.")
        return
    print(f"  {len(targets)} rows to backfill")
    print(f"  First: id={targets[0][0]} pn={targets[0][1]} pt={targets[0][2]}")
    print(f"  Last:  id={targets[-1][0]} pn={targets[-1][1]} pt={targets[-1][2]}")
    print(f"  Concurrency: {args.concurrency}")

    queue: asyncio.Queue = asyncio.Queue()
    for t in targets:
        await queue.put(t)
    for _ in range(args.concurrency):
        await queue.put(None)

    results = {"updated": 0, "misses": 0, "errors": 0, "timeouts": 0,
               "total": len(targets), "t0": time.time()}

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
    print(f"  misses     : {results['misses']}  (no detail page returned)")
    print(f"  errors     : {results['errors']}")
    print(f"  timeouts   : {results['timeouts']}")
    print(f"  elapsed    : {elapsed:.0f}s  ({results['updated'] / max(1, elapsed):.1f} updates/s)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
