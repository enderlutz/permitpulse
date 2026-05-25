"""Geocode permits that don't yet have lat/lng using the Census batch geocoder.

Defaults tuned for production reliability:
  - Batches of 100 (smaller batches = higher per-batch success rate, more
    granular retry surface area, less work lost when Census throttles).
  - 2-second pause between batches (politeness + throttle avoidance).
  - Per-batch reporting so daily-cron logs surface degradation early.
  - Continues past a single low-match batch (Census's silent throttling is
    transient — but if 5 batches in a row come back near-empty we bail
    so we don't waste compute on a brick wall).

Run from `backend/`:
    python -m scripts.geocode_permits --limit 5000
    python -m scripts.geocode_permits --limit 5000 --batch-size 100 --delay 2
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SessionLocal  # noqa: E402
from models import Permit  # noqa: E402
from services.geocoding import geocode_batch  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--batch-size", type=int, default=100,
                   help="Census likes smaller batches under load (default 100, max 10000)")
    p.add_argument("--delay", type=float, default=2.0,
                   help="Seconds to pause between batches (default 2.0)")
    p.add_argument("--bail-threshold", type=int, default=5,
                   help="Stop if this many consecutive batches return <5%% matches")
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
        if not pending:
            print("No ungeocoded permits with addresses found.")
            return

        print(f"Geocoding {len(pending)} permits in batches of {args.batch_size} "
              f"(delay {args.delay}s, bail after {args.bail_threshold} consecutive low-match batches)")
        print()

        total_matched = 0
        consecutive_low = 0
        n_batches = (len(pending) + args.batch_size - 1) // args.batch_size

        for i in range(0, len(pending), args.batch_size):
            batch = pending[i : i + args.batch_size]
            batch_num = i // args.batch_size + 1
            inputs = [(str(perm.id), perm.address) for perm in batch if perm.address]

            result = geocode_batch(inputs)
            for perm in batch:
                if str(perm.id) in result:
                    lat, lng = result[str(perm.id)]
                    perm.latitude = lat
                    perm.longitude = lng
            db.commit()

            n_matched = len(result)
            n_sent = len(inputs)
            rate = (n_matched / max(n_sent, 1)) * 100
            total_matched += n_matched

            status = "✓" if rate >= 20 else ("·" if rate >= 5 else "⚠")
            print(f"  {status} Batch {batch_num:>3}/{n_batches}: {n_matched:>3}/{n_sent} ({rate:>4.1f}%)")

            if rate < 5:
                consecutive_low += 1
                if consecutive_low >= args.bail_threshold:
                    print()
                    print(f"⚠ Bailing — {args.bail_threshold} consecutive batches returned <5% matches.")
                    print(f"  Census is likely throttling. Re-run in 15-30 min.")
                    print(f"  Total matched so far: {total_matched}/{i + n_sent}")
                    return
            else:
                consecutive_low = 0

            # Be polite between batches
            if i + args.batch_size < len(pending):
                time.sleep(args.delay)

        rate = (total_matched / len(pending)) * 100
        print()
        print(f"Done — matched {total_matched}/{len(pending)} ({rate:.1f}%)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
