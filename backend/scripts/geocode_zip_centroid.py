"""Layer 3 of the 99%-geocode push: fall back to ZIP centroid for rows that
both Census and Nominatim failed to find.

These are typically private streets, brand-new subdivisions whose street
names aren't in either dataset yet, or non-address-shaped utility
descriptions. We drop a pin at the ZIP centroid so they still show on the
map (as clustered markers), tagged with geo_precision = 'zip' so the
frontend can render them differently from rooftop matches.

ZIP centroids come from the Census Geocoder's ZIP-level lookup, cached
locally after first fetch since Houston-area ZIP centroids don't move.

Run from `backend/`:
    python -m scripts.geocode_zip_centroid
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import engine  # noqa: E402


# Add geo_precision column on first run.
def ensure_schema():
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE permits ADD COLUMN IF NOT EXISTS geo_precision VARCHAR"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_permits_geo_precision ON permits(geo_precision)"
        ))


def fetch_zip_centroids_from_db() -> dict[str, tuple[float, float]]:
    """Derive ZIP centroids from rows we ALREADY successfully geocoded.
    No external lookup needed — averaging existing precise points per ZIP
    produces a reasonable centroid for the area, naturally weighted toward
    where permitted activity actually clusters."""
    out: dict[str, tuple[float, float]] = {}
    with engine.connect() as c:
        for r in c.execute(text("""
            SELECT zip_code,
                   AVG(latitude) AS lat,
                   AVG(longitude) AS lng,
                   COUNT(*) AS n
            FROM permits
            WHERE latitude IS NOT NULL AND zip_code IS NOT NULL
            GROUP BY zip_code
            HAVING COUNT(*) >= 3
        """)):
            out[r[0]] = (float(r[1]), float(r[2]))
    return out


def fetch_zip_centroid_from_census(client: httpx.Client, zip_code: str) -> tuple[float, float] | None:
    """Fallback when our DB has no precise points for this ZIP yet.
    Uses Census's onelineaddress geocoder with just the ZIP."""
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    params = {
        "address": zip_code,
        "benchmark": "Public_AR_Current",
        "format": "json",
    }
    try:
        r = client.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        matches = data.get("result", {}).get("addressMatches", [])
        if matches:
            c = matches[0].get("coordinates", {})
            if "y" in c and "x" in c:
                return (float(c["y"]), float(c["x"]))
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        return None
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Report counts without writing")
    args = p.parse_args()

    ensure_schema()

    # Mark every existing geocoded row as rooftop precision (idempotent).
    with engine.begin() as conn:
        r = conn.execute(text("""
            UPDATE permits SET geo_precision = 'rooftop'
            WHERE latitude IS NOT NULL AND geo_precision IS NULL
        """))
        print(f"Tagged {r.rowcount:,} existing geocoded rows as geo_precision='rooftop'")

    # Pull ungeocoded rows with a ZIP.
    with engine.connect() as c:
        targets = list(c.execute(text("""
            SELECT id, zip_code FROM permits
            WHERE latitude IS NULL AND zip_code IS NOT NULL
        """)))
    print(f"Found {len(targets):,} ungeocoded rows with a ZIP")
    if not targets:
        return

    # Derive centroids from our own well-geocoded data first.
    centroids = fetch_zip_centroids_from_db()
    print(f"Have centroids for {len(centroids):,} ZIPs from existing data")

    # Fetch any missing ZIPs from Census (rare — usually our DB covers them).
    needed_zips = {z for _, z in targets} - set(centroids)
    if needed_zips:
        print(f"Fetching {len(needed_zips):,} missing ZIP centroids from Census...")
        with httpx.Client(headers={"User-Agent": "permit-pulse/0.1"}) as client:
            for i, z in enumerate(sorted(needed_zips), 1):
                latlng = fetch_zip_centroid_from_census(client, z)
                if latlng:
                    centroids[z] = latlng
                time.sleep(0.3)
                if i % 20 == 0:
                    print(f"  {i}/{len(needed_zips)} fetched")

    # Apply.
    by_zip: dict[str, list[int]] = {}
    for pid, z in targets:
        if z in centroids:
            by_zip.setdefault(z, []).append(pid)

    total_to_write = sum(len(v) for v in by_zip.values())
    print(f"Will tag {total_to_write:,} rows with ZIP-centroid coordinates")

    if args.dry_run:
        print("(dry-run — no writes)")
        return

    with engine.begin() as conn:
        for z, ids in by_zip.items():
            lat, lng = centroids[z]
            conn.execute(
                text("""
                    UPDATE permits
                    SET latitude = :lat, longitude = :lng, geo_precision = 'zip'
                    WHERE id = ANY(:ids) AND latitude IS NULL
                """),
                {"lat": lat, "lng": lng, "ids": ids},
            )
    print(f"Tagged {total_to_write:,} rows.")


if __name__ == "__main__":
    main()
