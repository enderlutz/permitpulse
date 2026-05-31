"""Populate permits.permit_nature for every row from permit_type + comments.

permit_nature is what the cross-source "Building" filter keys on (City of
Houston and Harris County type their permits with totally different vocab, so
an exact permit_type match can't span both — permit_nature can).

Adds the column if it's missing (create_all won't ALTER an existing table),
then classifies every row. Idempotent — safe to re-run / schedule.

Run from `backend/`:
    python -m scripts.backfill_permit_nature            # dry-run (counts only)
    python -m scripts.backfill_permit_nature --apply
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from db import engine  # noqa: E402
from schemas import classify_permit_nature  # noqa: E402


def ensure_column():
    is_sqlite = engine.dialect.name == "sqlite"
    with engine.begin() as conn:
        if is_sqlite:
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(permits)"))]
            if "permit_nature" not in cols:
                conn.execute(text("ALTER TABLE permits ADD COLUMN permit_nature VARCHAR"))
        else:
            conn.execute(text("ALTER TABLE permits ADD COLUMN IF NOT EXISTS permit_nature VARCHAR"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_permits_permit_nature ON permits (permit_nature)"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all", action="store_true", help="Re-classify every row (default: only NULL permit_nature)")
    args = ap.parse_args()

    ensure_column()

    with engine.connect() as c:
        where = "" if args.all else "WHERE permit_nature IS NULL"
        rows = c.execute(text(f"SELECT id, permit_type, comments FROM permits {where}")).all()
    print(f"Examining {len(rows)} rows...")

    updates, counts = [], Counter()
    for r in rows:
        nat = classify_permit_nature(r.permit_type, r.comments)
        counts[nat] += 1
        updates.append({"id": r.id, "n": nat})

    print("permit_nature distribution:")
    for k, v in counts.most_common():
        print(f"  {str(k):>14}  {v}")

    if not args.apply:
        print("\nDry-run. Re-run with --apply to write.")
        return

    # Batch by nature value — one UPDATE ... WHERE id = ANY(array) per bucket
    # (≈8 round-trips total) instead of one per row.
    by_nature: dict[str | None, list[int]] = {}
    for u in updates:
        by_nature.setdefault(u["n"], []).append(u["id"])

    is_pg = engine.dialect.name != "sqlite"
    applied = 0
    with engine.begin() as conn:
        for nat, ids in by_nature.items():
            if nat is None:
                continue  # leave unclassifiable rows NULL
            CH = 10000
            for i in range(0, len(ids), CH):
                chunk = ids[i:i + CH]
                if is_pg:
                    conn.execute(
                        text("UPDATE permits SET permit_nature = :n WHERE id = ANY(:ids)"),
                        {"n": nat, "ids": chunk},
                    )
                else:
                    ph = ",".join(str(x) for x in chunk)
                    conn.execute(text(f"UPDATE permits SET permit_nature = '{nat}' WHERE id IN ({ph})"))
                applied += len(chunk)
            print(f"  set {nat}: {len(ids)}")
    print(f"\nApplied permit_nature to {applied} rows.")


if __name__ == "__main__":
    main()
