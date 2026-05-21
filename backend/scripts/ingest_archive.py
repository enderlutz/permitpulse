"""Download + parse Houston Public Works weekly Permit eReport xlsx files,
load into the configured database.

Run from `backend/`:
    python -m scripts.ingest_archive --start 2024-01-01 --end 2025-11-30

URL pattern:
    https://www.houstontx.gov/planning/DevelopRegs/docs_pdfs/Permit_eReport/{YYYY}/Web-eReport-Permits-{MM}-{DD}-{YYYY}.xlsx

Reports are weekly, typically dated Mondays. Series ended Nov 24 2025.
"""
import argparse
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import httpx
from sqlalchemy import insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import engine, Base, SessionLocal  # noqa: E402
from models import Permit  # noqa: E402
from services.ingestion import parse_xlsx  # noqa: E402


BASE_URL = "https://www.houstontx.gov/planning/DevelopRegs/docs_pdfs/Permit_eReport"


def mondays_between(start: date, end: date):
    d = start
    # snap to Monday
    while d.weekday() != 0:
        d += timedelta(days=1)
    while d <= end:
        yield d
        d += timedelta(days=7)


def url_for(d: date) -> str:
    return f"{BASE_URL}/{d.year}/Web-eReport-Permits-{d.month:02d}-{d.day:02d}-{d.year}.xlsx"


def download(d: date, client: httpx.Client, tmpdir: Path) -> Path | None:
    url = url_for(d)
    try:
        r = client.get(url, timeout=30)
    except httpx.HTTPError as e:
        print(f"  ✗ {d} network error: {e}")
        return None
    if r.status_code != 200 or len(r.content) < 5000:
        return None
    path = tmpdir / f"{d.isoformat()}.xlsx"
    path.write_bytes(r.content)
    return path


def upsert(rows: list[dict]) -> int:
    if not rows:
        return 0
    # SQLAlchemy upsert on project_no
    is_sqlite = engine.dialect.name == "sqlite"
    with engine.begin() as conn:
        if is_sqlite:
            stmt = sqlite_insert(Permit).values(rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["project_no"])
        else:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(Permit).values(rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["project_no"])
        conn.execute(stmt)
    return len(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--end", default="2025-11-30")
    args = p.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    Base.metadata.create_all(bind=engine)

    print(f"Ingesting Houston permit eReports {start} → {end}")
    weeks = list(mondays_between(start, end))
    print(f"  {len(weeks)} weekly files to attempt")

    total_rows = 0
    successful_files = 0
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        with httpx.Client(headers={"User-Agent": "permit-pulse/0.1"}) as client:
            for d in weeks:
                # try Monday, fall back to nearby weekdays if 404
                paths = []
                for offset in (0, -3, 3, -1, 1, -2, 2):
                    dd = d + timedelta(days=offset)
                    path = download(dd, client, tmpdir)
                    if path:
                        paths.append(path)
                        break
                if not paths:
                    print(f"  - {d} no file found")
                    continue
                path = paths[0]
                try:
                    rows = [r for r in parse_xlsx(path) if r["project_no"]]
                except Exception as e:
                    print(f"  ✗ {d} parse error: {e}")
                    continue
                inserted = upsert(rows)
                total_rows += inserted
                successful_files += 1
                print(f"  ✓ {d}  {len(rows):5d} rows")

    print(f"\nDone. {successful_files}/{len(weeks)} files ingested, {total_rows} permits total.")


if __name__ == "__main__":
    main()
