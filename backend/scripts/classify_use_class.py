"""Populate use_class for permits where it's NULL by keyword-scanning the
permit description + project description. Currently ~81% of rows have no
use_class — this is the simplest and most effective fix to unlock filtering
and segmentation in the dashboard.

Priority-ordered matching: the first rule that hits wins. More specific
categories (restaurant, clinic) come before general ones (commercial) so
that "COMMERCIAL RESTAURANT 1,500 SF" classifies as restaurant.

Run from `backend/`:
    python -m scripts.classify_use_class            # dry-run
    python -m scripts.classify_use_class --apply
"""
import argparse
import re
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_, update  # noqa: E402

from db import SessionLocal  # noqa: E402
from models import Permit  # noqa: E402


# Order matters — more specific first. Each rule is (label, regex).
#
# Notes from audit on 2026-05-28:
#  - permit_type often carries Houston-specific codes that incidentally
#    contain English words ("C/W STORE BILL" is a dumpster-permit type
#    code, not a retail "store"). Classifying off comments only avoids
#    those false positives.
#  - "FACTORY" alone catches "FACTORY SALON" (a salon-chain brand). Use
#    "MANUFACTURING PLT" / "INDUSTRIAL BLDG" instead so only real
#    industrial sites match.
#  - "STORE" / "SHOP" / "MART" / "SUITE" are too generic — replaced with
#    distinct retail/office descriptors. "C-STORE" + "CONVENIENCE STORE"
#    cover convenience stores explicitly without false-positive risk.
RULES: list[tuple[str, re.Pattern]] = [
    ("restaurant", re.compile(r"\b(RESTAURANT|TAQUERIA|PIZZERIA|PIZZA SHOP|CAFE|CAFÉ|GRILL|BURGER|KITCHEN REMODEL|EATERY|BISTRO|STEAKHOUSE|BAKERY|DELI|DINER|SUSHI|RAMEN|FOOD COURT|COFFEE SHOP)\b", re.I)),
    ("hotel",      re.compile(r"\b(HOTEL|MOTEL|RESORT|HOLIDAY INN|MARRIOTT|HILTON|HYATT)\b", re.I)),
    ("clinic",     re.compile(r"\b(CLINIC|MEDICAL OFFICE|HOSPITAL|DENTAL OFFICE|URGENT CARE|PHARMACY|PEDIATRIC|VETERINARY)\b", re.I)),
    ("school",     re.compile(r"\b(SCHOOL|UNIVERSITY|COLLEGE|ACADEMY|CLASSROOM|ISD|DAYCARE|PRESCHOOL)\b", re.I)),
    ("church",     re.compile(r"\b(CHURCH|TEMPLE|MOSQUE|SYNAGOGUE|CHAPEL|CATHEDRAL|PARISH)\b", re.I)),
    ("warehouse",  re.compile(r"\b(WAREHOUSE|WHSE|NEW WHSE|STORAGE FACIL|STORAGE BLDG|DISTRIBUTION CTR|DISTRIBUTION CENTER|FULFILLMENT|LOGISTICS CTR|MANUFACTURING PLT|INDUSTRIAL BLDG)\b", re.I)),
    ("retail",     re.compile(r"\b(RETAIL|SHOPPING CTR|SHOPPING CENTER|STRIP CTR|MALL|BOUTIQUE|SHOWROOM|DEALERSHIP|C-STORE|CONVENIENCE STORE|GAS STATION)\b", re.I)),
    ("office",     re.compile(r"\b(OFFICE BLDG|OFFICE REMODEL|OFFICE BUILDOUT|COWORKING|HEADQUARTERS|CORPORATE HQ|PROFESSIONAL BLDG)\b", re.I)),
    ("apartment",  re.compile(r"\b(APARTMENT|APT BLDG|MULTI-FAMILY|MULTIFAMILY|MFU|TOWNHOM|CONDO|HIGH-RISE|MID-RISE|LOFT)\b", re.I)),
    ("residential",re.compile(r"\b(SF RES|SFR|SINGLE FAMILY|RESIDENTIAL DWELLING|NEW HOME|GARAGE|DRIVEWAY|FENCE|POOL|PATIO|DECK|REROOF)\b", re.I)),
    ("commercial", re.compile(r"\b(COMMERCIAL|MERCANTILE|TENANT FINISH|TENANT IMPROVEMENT)\b", re.I)),
    ("sign",       re.compile(r"\b(SIGN PLAN|SIGNAGE|BILLBOARD|ILLUM SIGN|NON-ILLUM SIGN)\b", re.I)),
    ("infrastructure", re.compile(r"\b(WW UTILITY|SEWER LINE|WATER LINE|FIRE HYDRANT|PAVING|ROADWAY|BRIDGE|DRAINAGE|MANHOLE|LIFT STN)\b", re.I)),
]


def classify(comments: str | None, permit_type: str | None = None) -> str | None:
    """Classify use_class by comments only — permit_type contains Houston
    codes that overlap English words and produce false positives.
    permit_type kept in the signature for backwards compatibility but ignored."""
    if not comments:
        return None
    for label, regex in RULES:
        if regex.search(comments):
            return label
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Write changes (default is dry-run)")
    p.add_argument("--all", action="store_true",
                   help="Re-classify ALL rows, not just NULL ones (use to refresh after rule changes)")
    p.add_argument("--sample", type=int, default=30)
    args = p.parse_args()

    db = SessionLocal()
    try:
        q = db.query(Permit.id, Permit.comments, Permit.permit_type, Permit.use_class)
        if not args.all:
            q = q.filter(Permit.use_class.is_(None))
        rows = q.all()
        print(f"Examining {len(rows)} rows...")

        changes: list[tuple[int, str | None, str | None]] = []
        counts: Counter = Counter()
        unmatched = 0
        for r in rows:
            new = classify(r.comments, r.permit_type)
            if new and new != r.use_class:
                changes.append((r.id, r.use_class, new))
                counts[new] += 1
            elif new is None:
                unmatched += 1

        print(f"Would set use_class on {len(changes)} rows")
        print(f"Unmatched (still NULL): {unmatched}")
        print()
        print("Class distribution from this run:")
        for label, n in counts.most_common():
            print(f"  {label:>15}  {n}")
        print()
        print(f"Sample (first {args.sample}):")
        for pid, before, after in changes[:args.sample]:
            print(f"  #{pid:>6}  {str(before):>10}  →  {after}")

        if not args.apply:
            print()
            print("Dry-run complete. Re-run with --apply to write changes.")
            return

        print()
        print("Applying...")
        applied = 0
        for pid, _b, after in changes:
            db.execute(update(Permit).where(Permit.id == pid).values(use_class=after))
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
