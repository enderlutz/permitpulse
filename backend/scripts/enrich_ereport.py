"""Enrich eReport-sourced permit rows with builder + project_value via the
sold_permit_d drill-down.

eReport rows have correct permit_date (from the weekly xlsx files) but no
builder, no value, and no FCC group — those fields only exist in the city's
Sold Permits Search. Those rows also carry permit_code = 'LEGACY' from the
pre-composite-key migration, so we don't know which sub-permit code to drill
with. We try a short list of common codes (PX is the safest first guess —
nearly every project has a Plan Review Fee record) until one returns a
Project Details page.

Run from `backend/`:
    python -m scripts.enrich_ereport --concurrency 5
    python -m scripts.enrich_ereport --limit 200
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
from services.sold_permits_scraper import (  # noqa: E402
    fetch_project_detail,
    COMMON_PT_CANDIDATES,
)


# Ordered by hit-likelihood on Houston permits. PX (Plan Review Fee) is almost
# universally present; 13 (Building Pmt) covers most new-construction projects;
# BU is the old building-permit type; 11/12/14 catch electrical/plumbing/HVAC
# projects without a building permit. We stop at the first hit.
PT_PROBE_ORDER = ["PX", "13", "BU", "11", "12", "14", "CC", "BX", "GI", "CO", "S9", "FF", "WK"]


def fetch_targets(limit: int | None = None, since_id: int | None = None) -> list[tuple[int, str]]:
    """eReport rows missing builder OR project_value. Each project_no appears
    exactly once in eReport data (single LEGACY row per project), so this
    is also the unique-project list."""
    sql = """
        SELECT id, project_no
        FROM permits
        WHERE source = 'houston_ereport'
          AND project_no IS NOT NULL
          AND (builder IS NULL OR project_value IS NULL)
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
    """Fill builder + project_value when NULL. Do NOT touch permit_date —
    eReport's date came from the weekly xlsx and is already authoritative."""
    set_clauses = []
    params: dict = {"id": row_id}
    if detail.get("owner"):
        set_clauses.append("builder = COALESCE(builder, :builder)")
        params["builder"] = detail["owner"]
    if detail.get("project_value") is not None:
        set_clauses.append("project_value = COALESCE(project_value, :project_value)")
        params["project_value"] = detail["project_value"]
    if not set_clauses:
        return
    stmt = text(f"UPDATE permits SET {', '.join(set_clauses)} WHERE id = :id")
    with engine.begin() as conn:
        conn.execute(stmt, params)


async def probe_project(client: httpx.AsyncClient, pn: str) -> dict | None:
    """Try the candidate PTs until one returns a Project Details page."""
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
                results["enriched"] += 1
                if results["enriched"] % 100 == 0:
                    rate = results["enriched"] / max(1, time.time() - results["t0"])
                    eta_m = (results["total"] - results["processed"]) / max(rate, 0.01) / 60
                    print(f"  [{name}] enriched {results['enriched']}/{results['total']} "
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

    print("Fetching eReport rows missing builder/value...")
    targets = fetch_targets(limit=args.limit, since_id=args.since_id)
    if not targets:
        print("Nothing to enrich.")
        return
    print(f"  {len(targets)} rows to enrich (concurrency={args.concurrency})")
    print(f"  First: id={targets[0][0]} pn={targets[0][1]}")
    print(f"  Last:  id={targets[-1][0]} pn={targets[-1][1]}")

    queue: asyncio.Queue = asyncio.Queue()
    for t in targets:
        await queue.put(t)
    for _ in range(args.concurrency):
        await queue.put(None)

    results = {"processed": 0, "enriched": 0, "unmatched": 0, "errors": 0,
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
    print(f"  enriched   : {results['enriched']}")
    print(f"  unmatched  : {results['unmatched']}  (no PT matched)")
    print(f"  errors     : {results['errors']}")
    print(f"  timeouts   : {results['timeouts']}")
    print(f"  elapsed    : {elapsed:.0f}s  ({results['enriched'] / max(1, elapsed):.1f}/s)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
