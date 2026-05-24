"""Enumerate Houston Sold Permits via Project Number lookup.

Strategy: walk plausible 26XXXXXX project numbers, render each in a headless
browser, upsert hits into Supabase / local SQLite. Smart-skips dead ranges
to keep the wall-clock reasonable.

Run from `backend/`:
    python -m scripts.scrape_sold_permits --start 26001001 --end 26025999 --concurrency 3
    python -m scripts.scrape_sold_permits --year 2026 --prefix-range 1 30
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import engine, Base  # noqa: E402
from models import Permit  # noqa: E402
from services.sold_permits_scraper import scrape_via_dom, to_permit_row  # noqa: E402


def candidates(start: int, end: int) -> list[str]:
    return [str(n) for n in range(start, end + 1)]


def prefix_range_candidates(year: int, prefix_lo: int, prefix_hi: int, max_seq: int = 999) -> list[str]:
    """Build a sweep across year + prefix + sequence."""
    out: list[str] = []
    for p in range(prefix_lo, prefix_hi + 1):
        for s in range(1, max_seq + 1):
            out.append(f"{year % 100:02d}{p:03d}{s:03d}")
    return out


def upsert_rows(rows: list[dict]) -> int:
    """Insert sub-permit rows for one project_no, replacing any LEGACY
    placeholder row that the migration left behind.

    Pre-migration data has a single LEGACY-coded row per project_no (a
    fallback so the composite unique constraint could be added without
    losing data). When we re-scrape that project, we have real per-permit
    codes, so the LEGACY row should be dropped first to avoid duplication.

    Each call is atomic — delete + insert in one transaction per project.
    """
    if not rows:
        return 0
    is_sqlite = engine.dialect.name == "sqlite"
    project_nos = sorted({r["project_no"] for r in rows if r.get("project_no")})

    with engine.begin() as conn:
        if project_nos:
            del_stmt = text(
                "DELETE FROM permits "
                "WHERE permit_code = 'LEGACY' AND project_no IN :pns"
            ).bindparams(bindparam("pns", expanding=True))
            conn.execute(del_stmt, {"pns": project_nos})
        if is_sqlite:
            stmt = sqlite_insert(Permit).values(rows).on_conflict_do_nothing(
                index_elements=["project_no", "permit_code"]
            )
        else:
            stmt = pg_insert(Permit).values(rows).on_conflict_do_nothing(
                index_elements=["project_no", "permit_code"]
            )
        conn.execute(stmt)
    return len(rows)


QUERY_TIMEOUT_SECS = 90  # Hard ceiling per query — kills hung Playwright instances


async def worker(name: str, queue: asyncio.Queue, results: dict):
    while True:
        pn = await queue.get()
        if pn is None:
            queue.task_done()
            return
        try:
            # Hard timeout per query so a single hung Playwright doesn't
            # silently block the worker forever (this happened on 2026-05-24
            # — 6 jobs sat idle for an hour with no insertions).
            try:
                r = await asyncio.wait_for(scrape_via_dom(pn), timeout=QUERY_TIMEOUT_SECS)
            except asyncio.TimeoutError:
                results["errors"] += 1
                print(f"  [{name}] ✗ {pn} hard-timeout after {QUERY_TIMEOUT_SECS}s — skipping")
                continue
            results["queried"] += 1
            if r["status"] == "hit" and r.get("rows"):
                normalized = [to_permit_row(row) for row in r["rows"]]
                normalized = [n for n in normalized if n.get("project_no") and n["project_no"][0].isdigit()]
                if normalized:
                    upsert_rows(normalized)
                    results["hits"] += 1
                    results["records"] += len(normalized)
                    print(f"  [{name}] ✓ {pn}  {len(normalized)} records  ({results['queried']}/{results['total']})")
            elif r["status"] == "miss":
                results["misses"] += 1
                if results["queried"] % 25 == 0:
                    print(f"  [{name}] · {pn} miss  ({results['queried']}/{results['total']} so far, {results['hits']} hits)")
            else:
                results["errors"] += 1
                print(f"  [{name}] ✗ {pn} {r['status']}: {r.get('error', '')}")
        except Exception as e:
            results["errors"] += 1
            print(f"  [{name}] ✗ {pn} exception: {type(e).__name__}: {e}")
        finally:
            queue.task_done()


def latest_seen_project_no(year: int) -> int | None:
    """Highest project_no currently in the DB that starts with this year's
    2-digit prefix. Returns None if no rows for the year."""
    from sqlalchemy import func
    from sqlalchemy.orm import Session
    yy = f"{year % 100:02d}"
    with Session(engine) as s:
        m = (
            s.query(func.max(Permit.project_no))
            .filter(Permit.project_no.like(f"{yy}%"))
            .scalar()
        )
        if m is None:
            return None
        try:
            return int(m)
        except (ValueError, TypeError):
            return None


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=int, help="First project number to query (e.g. 26001001)")
    p.add_argument("--end", type=int, help="Last project number to query (inclusive)")
    p.add_argument("--year", type=int, help="Year (last 2 digits used) for prefix-range mode")
    p.add_argument("--prefix-range", nargs=2, type=int, metavar=("LO", "HI"),
                   help="Prefix range to sweep (e.g. 1 30 → 26001xxx-26030xxx)")
    p.add_argument("--from-latest", type=int, metavar="N",
                   help="Incremental mode: scrape the next N candidates after the highest "
                        "project_no already in the DB for the current year. Designed for the daily cron.")
    p.add_argument("--year-for-latest", type=int, default=2026,
                   help="Year prefix to use with --from-latest (default 2026)")
    p.add_argument("--max-seq", type=int, default=999,
                   help="Max sequence number to try per prefix (default 999)")
    p.add_argument("--concurrency", type=int, default=3, help="Parallel browsers (default 3)")
    args = p.parse_args()

    Base.metadata.create_all(bind=engine)

    if args.start and args.end:
        cands = candidates(args.start, args.end)
    elif args.year and args.prefix_range:
        cands = prefix_range_candidates(args.year, args.prefix_range[0], args.prefix_range[1], args.max_seq)
    elif args.from_latest:
        latest = latest_seen_project_no(args.year_for_latest)
        if latest is None:
            print(f"No rows yet for year {args.year_for_latest} — start with --start/--end.")
            return
        start = latest + 1
        end = start + args.from_latest - 1
        print(f"Incremental mode: latest seen = {latest}, scraping {start}..{end}")
        cands = candidates(start, end)
    else:
        p.error("provide --start/--end, --year + --prefix-range, or --from-latest N")

    print(f"Sweeping {len(cands)} candidates with concurrency={args.concurrency}")
    print(f"First: {cands[0]}   Last: {cands[-1]}")

    queue: asyncio.Queue = asyncio.Queue()
    for c in cands:
        await queue.put(c)
    for _ in range(args.concurrency):
        await queue.put(None)

    results = {"queried": 0, "hits": 0, "misses": 0, "errors": 0, "records": 0, "total": len(cands)}
    t0 = time.time()
    workers = [asyncio.create_task(worker(f"W{i}", queue, results)) for i in range(args.concurrency)]
    await queue.join()
    for w in workers:
        await w
    elapsed = time.time() - t0

    print()
    print("=" * 60)
    print(f"  queried   : {results['queried']}")
    print(f"  hits      : {results['hits']}")
    print(f"  misses    : {results['misses']}")
    print(f"  errors    : {results['errors']}")
    print(f"  records   : {results['records']}")
    print(f"  elapsed   : {elapsed:.0f}s  ({elapsed/max(1, results['queried']):.1f}s/query)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
