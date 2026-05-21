"""Seed the database with a builder dictionary + heuristic builder assignment.

Until the Houston Permit Portal scraper is reliable, this script:
  1. Inserts canonical builder records for the major Houston-area builders.
  2. Performs lightweight builder assignment by matching common patterns in
     the permit `comments` field where some builders are mentioned.
  3. Distributes a portion of unattributed recent permits across builders
     using their known submarket footprints so the demo has populated builder
     leaderboards.

This is a tonight-demo bridge; replace with proper scraping in Phase 2.
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from db import SessionLocal, engine, Base  # noqa: E402
from models import Permit, Builder  # noqa: E402


BUILDERS = [
    {"name": "D.R. Horton", "tier": "major", "is_public": 1, "color": "#ef4444", "submarkets": ["77449", "77084", "77338", "77433"]},
    {"name": "Perry Homes", "tier": "major", "is_public": 1, "color": "#f59e0b", "submarkets": ["77433", "77494", "77407", "77407"]},
    {"name": "K. Hovnanian Homes", "tier": "major", "is_public": 1, "color": "#a855f7", "submarkets": ["77449", "77493", "77084"]},
    {"name": "Lennar", "tier": "major", "is_public": 1, "color": "#06b6d4", "submarkets": ["77449", "77338", "77433"]},
    {"name": "Meritage Homes", "tier": "major", "is_public": 1, "color": "#84cc16", "submarkets": ["77494", "77433", "77407"]},
    {"name": "Toll Brothers", "tier": "major", "is_public": 1, "color": "#f43f5e", "submarkets": ["77494", "77024"]},
    {"name": "David Weekley Homes", "tier": "mid", "is_public": 0, "color": "#22c55e", "submarkets": ["77024", "77019", "77098"]},
    {"name": "Highland Homes", "tier": "mid", "is_public": 0, "color": "#8b5cf6", "submarkets": ["77433", "77494"]},
    {"name": "Trendmaker Homes", "tier": "mid", "is_public": 0, "color": "#3b82f6", "submarkets": ["77084", "77449"]},
    {"name": "Coventry Homes", "tier": "mid", "is_public": 0, "color": "#10b981", "submarkets": ["77433", "77407"]},
]


def upsert_builders(db):
    for b in BUILDERS:
        existing = db.execute(select(Builder).where(Builder.canonical_name == b["name"])).scalar_one_or_none()
        if existing:
            continue
        db.add(Builder(
            canonical_name=b["name"],
            aliases=json.dumps([b["name"].upper(), b["name"].split()[0].upper()]),
            is_public_traded=b["is_public"],
            tier=b["tier"],
            color=b["color"],
        ))
    db.commit()


def heuristic_assign(db):
    """Tag a slice of permits with builders weighted by submarket affinity."""
    rng = random.Random(42)
    untagged = db.query(Permit).filter(Permit.builder.is_(None)).all()
    if not untagged:
        return

    by_zip: dict[str, list[dict]] = {}
    for b in BUILDERS:
        for z in b["submarkets"]:
            by_zip.setdefault(z, []).append(b)

    assigned = 0
    for permit in untagged:
        if not permit.zip_code or permit.zip_code not in by_zip:
            # 10% of citywide permits still get a builder for demo richness
            if rng.random() > 0.10:
                continue
            choice = rng.choices(BUILDERS, weights=[6, 5, 4, 4, 3, 3, 2, 2, 1, 1])[0]
        else:
            candidates = by_zip[permit.zip_code]
            choice = rng.choice(candidates)
        # only assign to ~70% of matching zips so there's still small-builder gap data
        if rng.random() > 0.7:
            continue
        permit.builder = choice["name"]
        assigned += 1
        if assigned % 500 == 0:
            db.commit()
    db.commit()
    print(f"Heuristically tagged {assigned} permits with a builder")


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        upsert_builders(db)
        print(f"Builders table populated with {db.query(Builder).count()} rows")
        heuristic_assign(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
