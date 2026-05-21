"""Geocode permits that don't yet have lat/lng using the Census batch geocoder.

Run from `backend/`:
    python -m scripts.geocode_permits --limit 5000
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SessionLocal  # noqa: E402
from models import Permit  # noqa: E402
from services.geocoding import geocode_batch  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--batch-size", type=int, default=500)
    args = p.parse_args()

    db = SessionLocal()
    try:
        pending = (
            db.query(Permit)
            .filter(Permit.latitude.is_(None), Permit.address.isnot(None))
            .order_by(Permit.permit_date.desc())
            .limit(args.limit)
            .all()
        )
        print(f"Geocoding {len(pending)} permits in batches of {args.batch_size}")

        for i in range(0, len(pending), args.batch_size):
            batch = pending[i : i + args.batch_size]
            inputs = [(str(p.id), p.address) for p in batch if p.address]
            print(f"  Batch {i // args.batch_size + 1}: posting {len(inputs)} addresses...")
            result = geocode_batch(inputs)
            for permit in batch:
                if str(permit.id) in result:
                    lat, lng = result[str(permit.id)]
                    permit.latitude = lat
                    permit.longitude = lng
            db.commit()
            print(f"     matched {len(result)}/{len(inputs)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
