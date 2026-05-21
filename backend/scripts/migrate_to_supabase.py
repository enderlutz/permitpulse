"""One-shot copy of every permit + builder row from local SQLite into a remote
Postgres (Supabase) database. Avoids the env-var quoting pitfalls of
`export DATABASE_URL=...` by taking the destination URL as a positional arg.

Usage (single quotes are critical — they prevent zsh from interpreting
characters in your password):

    python -m scripts.migrate_to_supabase 'postgresql://postgres:PWD@db.xxx.supabase.co:5432/postgres'
"""
import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import Permit, Builder, Base  # noqa: E402


def row_to_dict(row, columns):
    return {c: getattr(row, c) for c in columns}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dest_url", help="Destination Postgres URL (Supabase)")
    p.add_argument("--source", default="sqlite:///./permit_pulse.db", help="Source SQLite URL")
    p.add_argument("--chunk", type=int, default=1000)
    args = p.parse_args()

    if not args.dest_url.startswith("postgresql"):
        print("ERROR: dest_url must start with postgresql://", file=sys.stderr)
        sys.exit(1)

    print(f"Source : {args.source}")
    # mask password in displayed URL
    masked = args.dest_url
    if "@" in masked and ":" in masked.split("@", 1)[0]:
        prefix, rest = masked.split("@", 1)
        user, _ = prefix.rsplit(":", 1)
        masked = f"{user}:****@{rest}"
    print(f"Dest   : {masked}")

    src_engine = create_engine(args.source)
    dst_engine = create_engine(args.dest_url, pool_pre_ping=True)

    print("Creating tables on destination (if not present)...")
    Base.metadata.create_all(bind=dst_engine)

    builder_cols = ["canonical_name", "aliases", "is_public_traded", "tier", "color"]
    permit_cols = [
        "project_no", "permit_date", "permit_type", "address", "zip_code", "comments",
        "builder", "project_value", "square_feet", "use_class", "latitude", "longitude", "source",
    ]

    with Session(src_engine) as src, Session(dst_engine) as dst:
        # ---- Builders ----
        builders = src.query(Builder).all()
        print(f"Builders to copy: {len(builders)}")
        if builders:
            rows = [row_to_dict(b, builder_cols) for b in builders]
            stmt = pg_insert(Builder).values(rows).on_conflict_do_nothing(index_elements=["canonical_name"])
            dst.execute(stmt)
            dst.commit()
        print(f"  ✓ builders done")

        # ---- Permits ----
        total = src.query(func.count(Permit.id)).scalar() or 0
        print(f"Permits to copy: {total} (chunk size {args.chunk})")

        offset = 0
        copied = 0
        while True:
            batch = src.query(Permit).order_by(Permit.id).offset(offset).limit(args.chunk).all()
            if not batch:
                break
            rows = [row_to_dict(p, permit_cols) for p in batch]
            stmt = pg_insert(Permit).values(rows).on_conflict_do_nothing(index_elements=["project_no"])
            dst.execute(stmt)
            dst.commit()
            copied += len(batch)
            offset += args.chunk
            print(f"  {copied}/{total}")

        dst_count = dst.query(func.count(Permit.id)).scalar() or 0
        dst_geo = dst.query(func.count(Permit.id)).filter(Permit.latitude.isnot(None)).scalar() or 0
        dst_blds = dst.query(func.count(Permit.id)).filter(Permit.builder.isnot(None)).scalar() or 0
        print()
        print(f"Destination now has:")
        print(f"  permits: {dst_count}")
        print(f"  with lat/lng: {dst_geo}")
        print(f"  with builder: {dst_blds}")


if __name__ == "__main__":
    main()
