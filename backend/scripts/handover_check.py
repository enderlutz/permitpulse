"""Pre-handover health check — run before the client meeting.

Prints a single screen of headline numbers and flags any data integrity
issues left over from the night-of backfills. If any RED checks fail,
investigate before showing the dashboard.

Run from `backend/`:
    python -m scripts.handover_check
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from db import engine  # noqa: E402


def main():
    with engine.connect() as c:
        print("=" * 70)
        print("PERMIT-PULSE HANDOVER HEALTH CHECK")
        print("=" * 70)
        print()

        # ---- 1. Total row counts by source ----
        total = c.execute(text("SELECT COUNT(*) FROM permits")).scalar()
        by_source = list(c.execute(text("""
            SELECT source, COUNT(*) FROM permits GROUP BY source ORDER BY 2 DESC
        """)))
        print(f"Total permits: {total:,}")
        for src, n in by_source:
            print(f"  {src:30s} {n:>7,d}")
        print()

        # ---- 2. Date coverage ----
        date_min, date_max = c.execute(text(
            "SELECT MIN(permit_date), MAX(permit_date) FROM permits"
        )).fetchone()
        print(f"Date range: {date_min} → {date_max}")
        print()
        print("Monthly volume (last 12 months from max permit_date):")
        for r in c.execute(text("""
            SELECT to_char(permit_date,'YYYY-MM'), COUNT(*) FROM permits
            WHERE permit_date >= (SELECT MAX(permit_date) FROM permits) - INTERVAL '12 months'
            GROUP BY 1 ORDER BY 1
        """)):
            bar = "█" * (r[1] // 100)
            print(f"  {r[0]}  {r[1]:>5,d}  {bar}")
        print()

        # ---- 3. CHECK: any rows still on the bogus scrape-day cluster? ----
        bogus = c.execute(text("""
            SELECT COUNT(*) FROM permits
            WHERE source='houston_sold_permits'
              AND permit_date BETWEEN '2026-05-23' AND '2026-05-27'
        """)).scalar()
        if bogus < 50:
            print(f"✅ Date integrity: only {bogus} sold_permits rows still on scrape-day cluster")
        else:
            print(f"⚠️  Date integrity: {bogus} sold_permits rows still have bogus 2026-05-23..27 dates")
            print(f"    Re-run backfill-dates.yml or backfill-legacy-dates.yml")
        print()

        # ---- 4. Field completeness ----
        print("Field coverage:")
        for col in ["builder", "canonical_builder", "project_value", "latitude", "use_class"]:
            r = c.execute(text(f"""
                SELECT COUNT(*) - COUNT({col}) AS missing,
                       ROUND(100.0 * COUNT({col}) / NULLIF(COUNT(*), 0), 1) AS pct
                FROM permits
            """)).fetchone()
            marker = "✅" if r[1] >= 80 else ("⚠️ " if r[1] >= 50 else "❌")
            print(f"  {marker} {col:22s} {r[1]:>5.1f}% populated  ({r[0]:,} missing)")
        print()

        # ---- 5. Top builders (the leaderboard) ----
        print("Top 10 builders (last 90 days, after canonicalization):")
        for r in c.execute(text("""
            SELECT COALESCE(canonical_builder, builder), COUNT(*) FROM permits
            WHERE permit_date >= (SELECT MAX(permit_date) FROM permits) - INTERVAL '90 days'
              AND builder IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10
        """)):
            print(f"  {r[0]:40s} {r[1]:>5d}")
        print()

        # ---- 6. Top hotspot ZIPs ----
        print("Top 10 ZIP hotspots (last 90 days):")
        for r in c.execute(text("""
            SELECT zip_code, COUNT(*) FROM permits
            WHERE permit_date >= (SELECT MAX(permit_date) FROM permits) - INTERVAL '90 days'
              AND zip_code IS NOT NULL
            GROUP BY zip_code ORDER BY 2 DESC LIMIT 10
        """)):
            print(f"  {r[0]:8s}  {r[1]:>5d}")
        print()

        # ---- 7. Headline KPIs (what the dashboard will show) ----
        ref = c.execute(text("SELECT MAX(permit_date) FROM permits")).scalar()
        for label, days in [("7-day", 7), ("30-day", 30), ("90-day", 90), ("365-day", 365)]:
            n = c.execute(text("""
                SELECT COUNT(*) FROM permits WHERE permit_date >= :start AND permit_date <= :ref
            """), {"start": ref - timedelta(days=days), "ref": ref}).scalar()
            print(f"  {label:8s}: {n:>6,d} permits")
        print()
        print("=" * 70)
        print("Ready for handover ✓" if bogus < 50 else "Still has cleanup pending ⚠️")
        print("=" * 70)


if __name__ == "__main__":
    main()
