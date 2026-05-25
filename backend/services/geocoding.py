"""Census Geocoder batch wrapper — production-grade reliability.

The Census batch endpoint is free and has no API key, but it has two annoying
failure modes that punish naive callers:

  1. **Silent throttling**: under load it returns a 200 with valid CSV but
     every row's match_flag is empty/'No_Match'. No error code, no header.
     The retry must treat "empty response across the whole batch" as a
     failure worth retrying.

  2. **Slow when stressed**: response time can balloon to 60-120s. Default
     httpx timeout needs to be generous.

This wrapper retries on both connection errors AND on "0 matches in a
non-empty batch", with exponential backoff. Final fallback: return whatever
partial matches we got and let the caller decide.
"""
import csv
import io
import time
from typing import Iterable, Optional

import httpx


CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BENCHMARK = "Public_AR_Current"


def _post_once(addresses: list[tuple[str, str]], city: str, state: str,
               timeout: float = 120.0) -> tuple[int, dict[str, tuple[float, float]]]:
    """One round-trip to Census. Returns (rows_seen, {id: (lat, lng)})."""
    buf = io.StringIO()
    w = csv.writer(buf)
    for row_id, addr in addresses:
        w.writerow([row_id, addr, city, state, ""])
    payload = buf.getvalue().encode()

    files = {"addressFile": ("addresses.csv", payload, "text/csv")}
    data = {"benchmark": BENCHMARK}

    with httpx.Client(timeout=timeout) as client:
        r = client.post(CENSUS_URL, files=files, data=data)
        r.raise_for_status()

    out: dict[str, tuple[float, float]] = {}
    rows_seen = 0
    for row in csv.reader(io.StringIO(r.text)):
        if len(row) < 6:
            continue
        rows_seen += 1
        row_id, _input, match_flag = row[0], row[1], row[2]
        coords = row[5] if len(row) > 5 else ""
        if match_flag == "Match" and coords and "," in coords:
            try:
                lng_str, lat_str = coords.split(",")
                out[row_id] = (float(lat_str), float(lng_str))
            except ValueError:
                continue
    return rows_seen, out


def geocode_batch(
    addresses: list[tuple[str, str]],
    city: str = "Houston",
    state: str = "TX",
    *,
    max_attempts: int = 4,
    min_match_rate: float = 0.05,
) -> dict[str, tuple[float, float]]:
    """Batch-geocode with throttling-aware retries.

    Returns {id: (lat, lng)} for successful matches.

    Retries when:
      - HTTP error (connection, timeout, 5xx) — exponential backoff
      - Census returns a 200 but match rate is below min_match_rate
        (almost certainly silent throttling — typical real rate is 30-60%)

    Final attempt returns whatever was matched, even if below threshold,
    so the caller still gets partial value.
    """
    if not addresses:
        return {}

    last_matches: dict[str, tuple[float, float]] = {}
    last_seen = 0
    for attempt in range(max_attempts):
        try:
            seen, matches = _post_once(addresses, city, state)
            last_seen, last_matches = seen, matches
            match_rate = (len(matches) / max(seen, 1)) if seen else 0
            # Good result: keep it
            if seen and match_rate >= min_match_rate:
                return matches
            # Suspicious (probably throttled) — backoff and retry, unless last attempt
            if attempt == max_attempts - 1:
                # Out of attempts; return whatever we have
                return matches
            wait = 5 * (2 ** attempt)  # 5, 10, 20, 40s
            time.sleep(wait)
        except httpx.HTTPError:
            if attempt == max_attempts - 1:
                # Give up — return partial matches from earlier attempts
                return last_matches
            time.sleep(5 * (2 ** attempt))

    return last_matches
