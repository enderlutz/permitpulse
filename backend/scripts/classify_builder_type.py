"""Tier-classify each permit's builder into one of four buckets:
  * 'national'    — known big production builder (D.R. Horton, Lennar, etc.)
  * 'local'       — other corporate entity (small builders, developers, LLCs)
  * 'individual'  — homeowner pulling a permit on their own house
  * 'unknown'     — pure punctuation / junk

Also writes a `canonical_builder` column that collapses name variants of
known national builders (e.g. "D.R. HORTON", "DR HORTON - TEXAS, LTD",
"D.R. HORTON - TEXASLTD" all become "D.R. Horton"). This is the biggest
visual quality win for the leaderboard — split entries become one.

Detection order (first match wins):
  1. Junk → 'unknown'
  2. Matches a NATIONAL_BUILDERS pattern → 'national' + canonical name
  3. Corporate token (LLC/INC/HOMES/etc.) or '&' → 'local'
  4. 2-4 ALPHA tokens looking like a person's name → 'individual'
  5. Default → 'local' (safer than hiding a real builder by mistake)

Run from `backend/`:
    python -m scripts.classify_builder_type            # dry-run
    python -m scripts.classify_builder_type --apply
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text, update  # noqa: E402

from db import SessionLocal, engine  # noqa: E402
from models import Permit  # noqa: E402


# Known national / large-regional production builders active in Houston.
# Each entry: (canonical display name, regex matching common variants).
# Order doesn't matter much — first match wins, but patterns are written
# specific enough to avoid cross-matching.
NATIONAL_BUILDERS: list[tuple[str, re.Pattern]] = [
    ("D.R. Horton",        re.compile(r"\bD\.?\s*R\.?\s*HORTON\b", re.I)),
    ("Lennar",             re.compile(r"\bLENNAR\b", re.I)),
    ("Perry Homes",        re.compile(r"\bPERRY\s+HOMES?\b", re.I)),
    ("Toll Brothers",      re.compile(r"\bTOLL\s+BROTHERS?\b", re.I)),
    ("David Weekley Homes",re.compile(r"\bDAVID\s+WEEKLEY\b", re.I)),
    ("K. Hovnanian Homes", re.compile(r"\bK\.?\s*HOVNANIAN\b", re.I)),
    ("Meritage Homes",     re.compile(r"\bMERITAGE\b", re.I)),
    ("Highland Homes",     re.compile(r"\bHIGHLAND\s+HOMES?\b", re.I)),
    ("Trendmaker Homes",   re.compile(r"\bTRENDMAKER\b", re.I)),
    ("Coventry Homes",     re.compile(r"\bCOVENTRY\s+HOMES?\b", re.I)),
    ("LGI Homes",          re.compile(r"\bLGI\s+HOMES?\b", re.I)),
    ("KB Home",            re.compile(r"\bKB\s+HOME\b", re.I)),
    ("PulteGroup",         re.compile(r"\b(PULTE|PULTEGROUP|PULTE\s+HOMES)\b", re.I)),
    ("Beazer Homes",       re.compile(r"\bBEAZER\b", re.I)),
    ("M/I Homes",          re.compile(r"\bM/?I\s+HOMES?\b", re.I)),
    ("Taylor Morrison",    re.compile(r"\bTAYLOR\s+MORRISON\b", re.I)),
    ("Century Communities",re.compile(r"\bCENTURY\s+COMMUNITIES\b", re.I)),
    ("Tri Pointe Homes",   re.compile(r"\bTRI\s*POINTE\b", re.I)),
    ("Westin Homes",       re.compile(r"\bWESTIN\s+HOMES?\b", re.I)),
    ("Chesmar Homes",      re.compile(r"\bCHESMAR\b", re.I)),
    ("Newmark Homes",      re.compile(r"\bNEWMARK\s+HOMES?\b", re.I)),
    ("Plantation Homes",   re.compile(r"\bPLANTATION\s+HOMES?\b", re.I)),
    ("McGuyer Homebuilders",re.compile(r"\bMCGUYER\b", re.I)),
    ("First America Homes",re.compile(r"\bFIRST\s+AMERICA\s+HOMES?\b", re.I)),
    ("Starlight Homes",    re.compile(r"\bSTARLIGHT\s+HOMES?\b", re.I)),
    ("History Maker Homes",re.compile(r"\bHISTORY\s*MAKER\b", re.I)),
    ("Saratoga Homes",     re.compile(r"\bSARATOGA\s+HOMES?\b", re.I)),
    ("Princeton Classic",  re.compile(r"\bPRINCETON\s+CLASSIC\b", re.I)),
    ("Long Lake",          re.compile(r"\bLONG\s+LAKE\b", re.I)),
    ("CastleRock Communities", re.compile(r"\bCASTLEROCK\b", re.I)),
]


def match_national(name: str) -> str | None:
    for canonical, pattern in NATIONAL_BUILDERS:
        if pattern.search(name):
            return canonical
    return None


CORPORATE_TOKENS = {
    "LLC", "L.L.C", "L.L.C.", "INC", "INC.", "CORP", "CORP.",
    "CO", "CO.", "LTD", "LTD.", "LP", "L.P.", "L.P", "PLLC",
    "TRUST", "GROUP", "HOMES", "HOME", "BUILDERS", "BUILDER",
    "DEVELOPMENT", "DEVELOPMENTS", "DEVELOP", "PROPERTIES",
    "PROPERTY", "INVESTMENTS", "INVESTMENT", "ENTERPRISES",
    "ENTERPRISE", "CONSTRUCTION", "REALTY", "CAPITAL", "HOLDINGS",
    "HOLDING", "PARTNERS", "PARTNERSHIP", "ASSOC", "ASSOCIATES",
    "ASSOCIATION", "FOUNDATION", "FND", "FND.", "MINISTRIES",
    "MINISTRY", "CHURCH", "CENTER", "CENTRE", "SCHOOL", "ISD",
    "UNIVERSITY", "COLLEGE", "HOSPITAL", "CLINIC", "INSTITUTE",
    "AUTHORITY", "DISTRICT", "COUNTY", "CITY", "STATE",
    "DEPARTMENT", "AGENCY", "BANK", "MANAGEMENT", "SERVICES",
    "SOLUTIONS", "SYSTEMS", "TECHNOLOGY", "INDUSTRIES", "VENTURES",
    "EQUITY", "FUND", "REIT", "PROJECT", "PLAZA", "TOWER", "TOWERS",
    "GALLERIA", "MARRIOTT", "HILTON", "HYATT", "HOTEL", "MOTEL",
    "PHARMACY", "CHEVRON", "EXXON", "WALGREENS", "CVS",
    "RESTAURANT", "TAQUERIA",
    # Multifamily / property-entity tokens — strong signals only.
    # Avoid common surnames (Park, Ridge, Grove, View, Vista) since the
    # classifier matches any token; using those risks misflagging real
    # individual names like "STEVEN PARK".
    "APARTMENTS", "APARTMENT", "APTS", "COMPLEX", "TOWNHOMES",
    "TOWNHOME", "CONDOMINIUMS", "CONDOMINIUM", "VENTURE",
    "VENTURES",
}


def _has_corporate_token(s: str) -> bool:
    upper = s.upper()
    # Strip punctuation for token check (but keep the originals in CORPORATE_TOKENS
    # for things like 'L.L.C.')
    tokens = set(re.findall(r"[A-Za-z\.]+", upper))
    return bool(tokens & CORPORATE_TOKENS)


# A clearly-individual name looks like 2-4 ALPHA tokens with no punctuation
# and no corporate tokens. Allow single-letter middle initials.
INDIVIDUAL_NAME_RE = re.compile(
    r"^[A-Z][A-Z'\-]+(?:\s+[A-Z][A-Z'\-]*\.?){1,3}\s*$"
)


def classify(name: str | None) -> tuple[str, str | None]:
    """Return (tier, canonical_name).

    tier ∈ {'national', 'local', 'individual', 'unknown'}.
    canonical_name is the deduplicated display name for national builders,
    None otherwise (use the original name).
    """
    if not name:
        return ("unknown", None)
    name = name.strip()
    if not name or len(re.sub(r"[^A-Za-z]", "", name)) < 3:
        return ("unknown", None)
    # 1. Known national builder?
    canonical = match_national(name)
    if canonical:
        return ("national", canonical)
    # 2. Partnership marker
    if "&" in name:
        return ("local", None)
    # 3. Has a corporate token
    if _has_corporate_token(name):
        return ("local", None)
    # 4. Individual name pattern
    if INDIVIDUAL_NAME_RE.match(name.upper()):
        return ("individual", None)
    # 5. Default: corporate-local (safer than hiding a real builder)
    return ("local", None)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--sample", type=int, default=30)
    args = p.parse_args()

    db = SessionLocal()
    try:
        # Ensure columns exist. Idempotent.
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE permits ADD COLUMN IF NOT EXISTS builder_type VARCHAR"
            ))
            conn.execute(text(
                "ALTER TABLE permits ADD COLUMN IF NOT EXISTS canonical_builder VARCHAR"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_permits_builder_type ON permits(builder_type)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_permits_canonical_builder ON permits(canonical_builder)"
            ))

        rows = db.query(Permit.id, Permit.builder).filter(Permit.builder.isnot(None)).all()
        print(f"Examining {len(rows)} permits with non-null builder...")

        changes: list[tuple[int, str, str, str | None]] = []
        counts: Counter = Counter()
        examples: dict[str, list[tuple[str, str | None, int]]] = {
            "national": [], "local": [], "individual": [], "unknown": []
        }
        for r in rows:
            tier, canonical = classify(r.builder)
            # Default canonical_builder to the original name when not a known national
            canonical_to_store = canonical or r.builder
            counts[tier] += 1
            changes.append((r.id, r.builder, tier, canonical_to_store))
            if len(examples[tier]) < 10:
                examples[tier].append((r.builder, canonical, r.id))

        print(f"Will tag {len(changes)} rows.")
        print()
        print("Tier distribution:")
        total = sum(counts.values()) or 1
        for label in ("national", "local", "individual", "unknown"):
            n = counts.get(label, 0)
            pct = 100 * n / total
            print(f"  {label:>12}: {n:>6} ({pct:.1f}%)")
        print()
        for label in ("national", "local", "individual", "unknown"):
            print(f"Examples of '{label}':")
            for name, canonical, pid in examples[label]:
                if canonical:
                    print(f"  #{pid:>6}  {name!r}  →  {canonical!r}")
                else:
                    print(f"  #{pid:>6}  {name!r}")
            print()

        if not args.apply:
            print("Dry-run. Re-run with --apply to write changes.")
            return

        print("Applying...")
        applied = 0
        for pid, _name, tier, canonical in changes:
            db.execute(
                update(Permit)
                .where(Permit.id == pid)
                .values(builder_type=tier, canonical_builder=canonical)
            )
            applied += 1
            if applied % 1000 == 0:
                db.commit()
                print(f"  {applied}/{len(changes)} committed")
        db.commit()
        print(f"Applied {applied} updates.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
