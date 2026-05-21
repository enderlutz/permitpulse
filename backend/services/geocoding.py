"""Census Geocoder batch wrapper.

POST a CSV with up to 10,000 addresses to /addressbatch, get back lat/lng.
Free, no API key, slower than commercial geocoders but fine for ingest jobs.
"""
import csv
import io
import time
from typing import Iterable, Optional

import httpx


CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BENCHMARK = "Public_AR_Current"


def geocode_batch(addresses: list[tuple[str, str]], city: str = "Houston", state: str = "TX") -> dict[str, tuple[float, float]]:
    """Geocode a batch. addresses is a list of (id, full_address) tuples.

    Returns {id: (lat, lng)} for successful matches.
    """
    if not addresses:
        return {}

    buf = io.StringIO()
    w = csv.writer(buf)
    for row_id, addr in addresses:
        w.writerow([row_id, addr, city, state, ""])
    buf.seek(0)

    files = {"addressFile": ("addresses.csv", buf.getvalue().encode(), "text/csv")}
    data = {"benchmark": BENCHMARK}

    with httpx.Client(timeout=120.0) as client:
        for attempt in range(3):
            try:
                r = client.post(CENSUS_URL, files=files, data=data)
                r.raise_for_status()
                break
            except httpx.HTTPError:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))

    out: dict[str, tuple[float, float]] = {}
    reader = csv.reader(io.StringIO(r.text))
    for row in reader:
        # Census format: id, input_addr, match_flag, match_type, matched_addr, coords, tiger_line_id, side
        if len(row) < 6:
            continue
        row_id = row[0]
        match_flag = row[2]
        coords = row[5] if len(row) > 5 else ""
        if match_flag == "Match" and coords and "," in coords:
            try:
                lng_str, lat_str = coords.split(",")
                out[row_id] = (float(lat_str), float(lng_str))
            except ValueError:
                continue
    return out
