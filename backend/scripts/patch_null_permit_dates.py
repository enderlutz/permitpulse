"""One-off: backfill permit_date for rows that were scraped before the
sold_permits_scraper started stamping one. Uses today as a proxy — same
default the scraper now uses for fresh rows.

Run from `backend/`:
    python -m scripts.patch_null_permit_dates
"""
import datetime
import sys
from pathlib import Path

from sqlalchemy import update

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import engine  # noqa: E402
from models import Permit  # noqa: E402


def main():
    today = datetime.date.today()
    with engine.begin() as conn:
        # Inspect first
        before = conn.execute(
            update(Permit)
            .where(Permit.source == "houston_sold_permits")
            .where(Permit.permit_date.is_(None))
            .values(permit_date=today)
        )
        print(f"Updated {before.rowcount} sold_permits rows with permit_date={today}")


if __name__ == "__main__":
    main()
