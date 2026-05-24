"""Classify each permit's builder as 'individual' (homeowner pulling a permit
for their own house) or 'corporate' (an actual builder, developer, or
business entity). Adds a new builder_type column to power a 'Real Builders
Only' toggle on the leaderboard.

Detection heuristics — all are LIKELY-individual signals:
  * Two-token names where the first token looks like a surname and the
    second like a first name (Houston ePermit shows owners as
    "LASTNAME FIRSTNAME" or "LASTNAME FIRSTNAME MIDDLE").
  * Common middle-initial patterns: "LASTNAME FIRSTNAME M" or
    "LASTNAME F M LASTNAME2" etc.

Corporate signals (override individual detection):
  * Starts with '*' in the raw ePermit data (already stripped by our
    normalizer; we re-check the underlying intent by looking for
    business-entity tokens).
  * Contains LLC, INC, CORP, CO, LTD, LP, PLLC, TRUST, GROUP, HOMES,
    BUILDERS, DEVELOPMENT, PROPERTIES, INVESTMENTS, ENTERPRISES,
    CONSTRUCTION, REALTY, CAPITAL, HOLDINGS, PARTNERS, ASSOC.
  * Contains '&' (e.g. SMITH & JONES) — typically a partnership.
  * Punctuation patterns: trailing ',' or contains '.' beyond a single
    middle initial.

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


CORPORATE_TOKENS = {
    "LLC", "L.L.C", "L.L.C.", "INC", "INC.", "CORP", "CORP.",
    "CO", "CO.", "LTD", "LTD.", "LP", "L.P.", "L.P", "PLLC",
    "TRUST", "GROUP", "HOMES", "HOME", "BUILDERS", "BUILDER",
    "DEVELOPMENT", "DEVELOPMENTS", "DEVELOP", "PROPERTIES",
    "PROPERTY", "INVESTMENTS", "INVESTMENT", "ENTERPRISES",
    "ENTERPRISE", "CONSTRUCTION", "REALTY", "CAPITAL", "HOLDINGS",
    "HOLDING", "PARTNERS", "PARTNERSHIP", "ASSOC", "ASSOCIATES",
    "ASSOCIATION", "FOUNDATION", "MINISTRIES", "MINISTRY", "CHURCH",
    "CENTER", "CENTRE", "SCHOOL", "ISD", "UNIVERSITY", "COLLEGE",
    "HOSPITAL", "CLINIC", "INSTITUTE", "AUTHORITY", "DISTRICT",
    "COUNTY", "CITY", "STATE", "DEPARTMENT", "AGENCY", "BANK",
    "MANAGEMENT", "SERVICES", "SOLUTIONS", "SYSTEMS", "TECHNOLOGY",
    "INDUSTRIES", "VENTURES", "EQUITY", "FUND", "REIT", "PROJECT",
    "PLAZA", "CENTER", "TOWER", "GALLERIA", "MARRIOTT", "HILTON",
    "HYATT", "HOTEL", "MOTEL", "PHARMACY", "CHEVRON", "EXXON",
    "WALGREENS", "CVS", "BANK", "RESTAURANT", "TAQUERIA",
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


def classify(name: str | None) -> str | None:
    if not name:
        return None
    name = name.strip()
    if not name:
        return None
    # Pure punctuation / single character → unknown
    if len(re.sub(r"[^A-Za-z]", "", name)) < 3:
        return "unknown"
    if "&" in name:
        return "corporate"
    if _has_corporate_token(name):
        return "corporate"
    if INDIVIDUAL_NAME_RE.match(name.upper()):
        # Quick guard: if it's all-caps and 2-4 tokens with no business words,
        # it's almost certainly a person.
        return "individual"
    # Default: when in doubt, mark corporate (safer for the leaderboard —
    # better to leave a real homeowner showing than to hide a real builder).
    return "corporate"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--sample", type=int, default=30)
    args = p.parse_args()

    db = SessionLocal()
    try:
        # Ensure column exists. Idempotent.
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE permits ADD COLUMN IF NOT EXISTS builder_type VARCHAR"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_permits_builder_type ON permits(builder_type)"
            ))

        rows = db.query(Permit.id, Permit.builder).filter(Permit.builder.isnot(None)).all()
        print(f"Examining {len(rows)} permits with non-null builder...")

        changes: list[tuple[int, str, str]] = []
        counts: Counter = Counter()
        examples: dict[str, list[tuple[str, int]]] = {"individual": [], "corporate": [], "unknown": []}
        for r in rows:
            label = classify(r.builder)
            if label:
                counts[label] += 1
                changes.append((r.id, r.builder, label))
                if len(examples[label]) < 10:
                    examples[label].append((r.builder, r.id))

        print(f"Will set builder_type on {len(changes)} rows.")
        print()
        print("Distribution:")
        total = sum(counts.values()) or 1
        for label, n in counts.most_common():
            pct = 100 * n / total
            print(f"  {label:>12}: {n:>6} ({pct:.1f}%)")
        print()
        for label in ("individual", "corporate", "unknown"):
            print(f"Examples of '{label}':")
            for name, pid in examples[label]:
                print(f"  #{pid:>6}  {name!r}")
            print()

        if not args.apply:
            print("Dry-run. Re-run with --apply to write changes.")
            return

        print("Applying...")
        applied = 0
        for pid, _name, label in changes:
            db.execute(update(Permit).where(Permit.id == pid).values(builder_type=label))
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
