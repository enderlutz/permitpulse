"""Layer 1 of the 99%-geocode push: clean ungeocoded addresses and retry Census.

Failure modes the existing geocode_permits pass leaves on the table:
  - Unit / apt / suite / building numbers tacked onto the end of the street
    address ("1001 E MEMORIAL LOOP DR 24", "300 E LITTLE YORK RD BLD 6")
  - Suffixes Census's parser chokes on ("VIA ISA (PVT) LN")
  - Non-address junk in the address field ("HCMUD#165-8112 FRY RD, 6\" WTR, ...")

Strategy:
  1. Pull all ungeocoded rows with an address.
  2. Apply heuristic cleaners — produce a candidate set per row.
  3. Batch-submit cleaned variants to Census; keep first match per row.

Run from `backend/`:
    python -m scripts.geocode_retry --limit 20000
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from db import engine  # noqa: E402
from services.geocoding import geocode_batch  # noqa: E402


# ---- Address cleaners ----------------------------------------------------

STREET_TYPES = (
    r"ST|STREET|AVE|AVENUE|BLVD|BOULEVARD|DR|DRIVE|RD|ROAD|LN|LANE|"
    r"WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|PKY|PKWY|PARKWAY|TRL|TRAIL|"
    r"HWY|HIGHWAY|XING|CROSSING|RUN|TER|TERRACE|LOOP|HOLLOW|HOLW|"
    r"CREEK|CRK|RIDGE|RDG|SPRINGS|SPGS|MEADOW|MDW|VALLEY|VLY"
)

# Strip a trailing unit / suite / apt / building marker, with or without #
UNIT_SUFFIX_RE = re.compile(
    r"\b(?:UNIT|APT|APARTMENT|STE|SUITE|BLDG|BUILDING|BLD|RM|ROOM|FL|FLOOR|#)\s*[A-Z0-9\-]+\s*$",
    re.I,
)

# Strip a trailing bare number that came after a street type, e.g. "LOOP DR 24"
# (24 is the unit). Captures numbers up to 4 digits to avoid eating a ZIP that
# slipped past the earlier ZIP-split in to_permit_row().
TRAILING_NUM_RE = re.compile(
    rf"(?P<street>\b(?:{STREET_TYPES})\b)\s+\d{{1,4}}[A-Z]?\s*$",
    re.I,
)

# (PVT) marker and parenthetical content Census's parser doesn't handle
PAREN_RE = re.compile(r"\s*\([^)]*\)\s*")

# Multiple spaces collapse
WS_RE = re.compile(r"\s+")

# Looks like address-y text (must start with digits and have a street type)
ADDRESS_LIKELY_RE = re.compile(
    rf"^\d+\s+\S+.*\b(?:{STREET_TYPES})\b",
    re.I,
)


def clean_variants(addr: str) -> list[str]:
    """Generate ordered cleaning attempts. First match wins downstream."""
    if not addr:
        return []
    base = addr.strip()
    variants: list[str] = []

    # If it doesn't even look like an address, bail.
    if not ADDRESS_LIKELY_RE.search(base):
        return []

    # Variant 0: as-is (already tried in main geocode pass, but Census is flaky
    # so a second try sometimes succeeds — included only if the row truly came
    # in untouched by us)
    variants.append(base)

    # Variant 1: strip explicit unit/suite marker
    v1 = UNIT_SUFFIX_RE.sub("", base).strip()
    if v1 != base:
        variants.append(v1)

    # Variant 2: strip a trailing bare number after a street type
    v2 = TRAILING_NUM_RE.sub(r"\g<street>", v1).strip()
    if v2 != v1:
        variants.append(v2)

    # Variant 3: drop parenthetical content like "(PVT)"
    v3 = WS_RE.sub(" ", PAREN_RE.sub(" ", v2)).strip()
    if v3 != v2:
        variants.append(v3)

    # Dedup while preserving order
    seen = set()
    out = []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


# ---- DB I/O --------------------------------------------------------------

def fetch_targets(limit: int | None) -> list[tuple[int, str, str | None]]:
    sql = """
        SELECT id, address, zip_code FROM permits
        WHERE latitude IS NULL AND address IS NOT NULL
        ORDER BY id
    """
    if limit:
        sql += f" LIMIT {limit}"
    with engine.connect() as c:
        return [tuple(r) for r in c.execute(text(sql))]


def write_back(matches: dict[int, tuple[float, float]]) -> int:
    if not matches:
        return 0
    with engine.begin() as conn:
        # Bulk via VALUES join — same pattern as the classify fast path
        rows = list(matches.items())
        CHUNK = 5000
        for i in range(0, len(rows), CHUNK):
            batch = rows[i:i + CHUNK]
            conn.execute(text("""
                CREATE TEMP TABLE IF NOT EXISTS _tmp_geo (id INT PRIMARY KEY, lat FLOAT, lng FLOAT) ON COMMIT DROP
            """))
            params = {}
            placeholders = []
            for j, (pid, (lat, lng)) in enumerate(batch):
                params[f"id_{j}"] = pid
                params[f"lat_{j}"] = lat
                params[f"lng_{j}"] = lng
                placeholders.append(f"(:id_{j}, :lat_{j}, :lng_{j})")
            conn.execute(
                text(f"INSERT INTO _tmp_geo (id, lat, lng) VALUES {','.join(placeholders)}"),
                params,
            )
        conn.execute(text("""
            UPDATE permits SET latitude = t.lat, longitude = t.lng
            FROM _tmp_geo t WHERE permits.id = t.id AND permits.latitude IS NULL
        """))
    return len(matches)


# ---- Main ----------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None,
                   help="Max rows to attempt this run")
    p.add_argument("--batch-size", type=int, default=100,
                   help="Census likes 100/batch")
    args = p.parse_args()

    targets = fetch_targets(args.limit)
    print(f"Loaded {len(targets):,} ungeocoded rows")
    if not targets:
        return

    # Build the list of (row_id, cleaned_addr) attempts. We attach a synthetic
    # ID combining permits.id and attempt index so we know which variant won
    # on the way back.
    attempts: list[tuple[str, str]] = []
    id_attempt_count: dict[int, int] = {}
    address_index: dict[str, int] = {}  # synthetic_id -> permits.id
    skipped = 0
    for pid, addr, _zip in targets:
        variants = clean_variants(addr)
        if not variants:
            skipped += 1
            continue
        for k, v in enumerate(variants):
            syn = f"{pid}-{k}"
            attempts.append((syn, v))
            address_index[syn] = pid
            id_attempt_count[pid] = id_attempt_count.get(pid, 0) + 1

    print(f"  {skipped:,} rows skipped (not address-shaped)")
    print(f"  {len(attempts):,} cleaning attempts queued")

    # Submit in chunks; flush DB writes every N batches so a kill doesn't
    # lose ~75 minutes of work.
    pending: dict[int, tuple[float, float]] = {}
    total_written = 0
    total = len(attempts)
    FLUSH_EVERY = 5  # ~500 rows / flush at batch_size=100
    n_batches = (total + args.batch_size - 1) // args.batch_size
    for bi, i in enumerate(range(0, total, args.batch_size), 1):
        batch = attempts[i:i + args.batch_size]
        result = geocode_batch(batch)
        for syn, latlng in result.items():
            pid = address_index.get(syn)
            if pid is not None and pid not in pending:
                pending[pid] = latlng
        print(f"  batch {bi:>3}/{n_batches}: "
              f"{total_written + len(pending):,} permits recovered so far", flush=True)
        if bi % FLUSH_EVERY == 0 and pending:
            total_written += write_back(pending)
            pending.clear()

    if pending:
        total_written += write_back(pending)
    print(f"\nMatched + wrote {total_written:,} rows "
          f"({100*total_written/max(len(targets),1):.1f}% of targets)")


if __name__ == "__main__":
    main()
