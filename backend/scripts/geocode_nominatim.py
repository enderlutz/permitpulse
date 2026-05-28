"""Layer 2 of the 99%-geocode push: fall back to OpenStreetMap's Nominatim
for rows Census couldn't match (even after geocode_retry's cleaning pass).

Nominatim is free and has wider coverage of new-construction subdivisions
than Census's TIGER/Line data, which often lags 1-2 years. Trade-off: 1
req/sec rate limit per the public-server TOS, so this is slow — ~3 hours
for 10k addresses.

We're polite: User-Agent identifies us, 1.1s sleep between requests,
exponential backoff on 429/5xx.

Run from `backend/`:
    python -m scripts.geocode_nominatim --limit 5000
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


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "permit-pulse/0.1 (bonneralan25@gmail.com)"  # required by Nominatim TOS
SLEEP = 1.1  # 1 req/sec rate limit


def fetch_targets(limit: int | None) -> list[tuple[int, str, str | None]]:
    """Rows we still don't have lat/lng for, with at least an address."""
    sql = """
        SELECT id, address, zip_code FROM permits
        WHERE latitude IS NULL AND address IS NOT NULL
        ORDER BY id
    """
    if limit:
        sql += f" LIMIT {limit}"
    with engine.connect() as c:
        return [tuple(r) for r in c.execute(text(sql))]


def query_nominatim(client: httpx.Client, addr: str, zip_code: str | None,
                    max_retries: int = 3) -> tuple[float, float] | None:
    """One Nominatim lookup. Returns (lat, lng) or None.

    Builds a structured query — street + city + state + zip — which tends
    to match better than a free-form text query for ambiguous street names.
    """
    params = {
        "street": addr,
        "city": "Houston",
        "state": "TX",
        "country": "USA",
        "format": "json",
        "limit": 1,
    }
    if zip_code:
        params["postalcode"] = zip_code

    for attempt in range(max_retries):
        try:
            r = client.get(NOMINATIM_URL, params=params, timeout=15)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
            if data and "lat" in data[0] and "lon" in data[0]:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
            return None
        except (httpx.HTTPError, ValueError, KeyError, IndexError):
            if attempt == max_retries - 1:
                return None
            time.sleep(2 * (attempt + 1))
    return None


def write_back(matches: dict[int, tuple[float, float]]) -> int:
    if not matches:
        return 0
    with engine.begin() as conn:
        rows = list(matches.items())
        CHUNK = 5000
        for i in range(0, len(rows), CHUNK):
            batch = rows[i:i + CHUNK]
            placeholders = []
            params = {}
            for j, (pid, (lat, lng)) in enumerate(batch):
                params[f"id_{j}"] = pid
                params[f"lat_{j}"] = lat
                params[f"lng_{j}"] = lng
                placeholders.append(f"(:id_{j}, :lat_{j}, :lng_{j})")
            conn.execute(text("""
                CREATE TEMP TABLE IF NOT EXISTS _tmp_geo (id INT PRIMARY KEY, lat FLOAT, lng FLOAT) ON COMMIT DROP
            """))
            conn.execute(
                text(f"INSERT INTO _tmp_geo (id, lat, lng) VALUES {','.join(placeholders)}"),
                params,
            )
        conn.execute(text("""
            UPDATE permits SET latitude = t.lat, longitude = t.lng
            FROM _tmp_geo t WHERE permits.id = t.id AND permits.latitude IS NULL
        """))
    return len(matches)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None,
                   help="Cap rows attempted (default: all)")
    p.add_argument("--report-every", type=int, default=50,
                   help="Print progress every N requests")
    args = p.parse_args()

    targets = fetch_targets(args.limit)
    print(f"Loaded {len(targets):,} ungeocoded rows for Nominatim pass")
    print(f"  Expected runtime: ~{len(targets) * SLEEP / 60:.0f} minutes "
          f"(1 req/sec rate limit)")
    if not targets:
        return

    pending: dict[int, tuple[float, float]] = {}
    total_matched = 0
    t0 = time.time()
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        for i, (pid, addr, zip_code) in enumerate(targets, 1):
            latlng = query_nominatim(client, addr, zip_code)
            if latlng:
                pending[pid] = latlng
            time.sleep(SLEEP)
            if i % args.report_every == 0:
                elapsed = time.time() - t0
                rate = i / elapsed
                eta_m = (len(targets) - i) / max(rate, 0.001) / 60
                seen_matches = total_matched + len(pending)
                hit_pct = 100 * seen_matches / i
                print(f"  {i:,}/{len(targets):,}  matches={seen_matches:,} ({hit_pct:.1f}%)  "
                      f"eta {eta_m:.1f}m", flush=True)
            # Flush periodically so a kill doesn't lose progress.
            if i % 200 == 0 and pending:
                total_matched += write_back(pending)
                pending.clear()

    if pending:
        total_matched += write_back(pending)
    print(f"\nNominatim pass complete. {total_matched:,} rows matched out of "
          f"{len(targets):,} ({100*total_matched/max(len(targets),1):.1f}%).")


if __name__ == "__main__":
    main()
