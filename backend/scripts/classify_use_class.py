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
RULES: list[tuple[str, re.Pattern]] = [
    ("restaurant", re.compile(r"\b(RESTAURANT|TAQUERIA|PIZZA|CAFE|CAFÉ|BAR|GRILL|BURGER|KITCHEN|EATERY|BISTRO|STEAKHOUSE|BAKERY|DELI|DINER|SUSHI|RAMEN)\b", re.I)),
    ("hotel",      re.compile(r"\b(HOTEL|MOTEL|INN|RESORT|SUITES|MARRIOTT|HILTON|HYATT|HOLIDAY INN)\b", re.I)),
    ("clinic",     re.compile(r"\b(CLINIC|MEDICAL|HOSPITAL|DENTAL|HEALTH CARE|HEALTHCARE|URGENT CARE|PHARMACY|PEDIATRIC|VETERINARY|ANIMAL)\b", re.I)),
    ("school",     re.compile(r"\b(SCHOOL|UNIVERSITY|COLLEGE|ACADEMY|EDUCATION|CLASSROOM|ISD|DAYCARE|PRESCHOOL|KINDERGARTEN)\b", re.I)),
    ("church",     re.compile(r"\b(CHURCH|TEMPLE|MOSQUE|SYNAGOGUE|CHAPEL|CATHEDRAL|MINISTRIES|PARISH|WORSHIP)\b", re.I)),
    ("warehouse",  re.compile(r"\b(WAREHOUSE|STORAGE FACIL|DISTRIBUTION|INDUSTRIAL|MANUFACTURING|FACTORY|FULFILLMENT|LOGISTICS)\b", re.I)),
    ("retail",     re.compile(r"\b(RETAIL|STORE|SHOP|MART|WALGREENS|CVS|MALL|SHOPPING|BOUTIQUE|SHOWROOM|DEALERSHIP)\b", re.I)),
    ("office",     re.compile(r"\b(OFFICE|COWORKING|HEADQUARTERS|HQ|CORPORATE|PROFESSIONAL BLDG|WORKSPACE|SUITE)\b", re.I)),
    ("apartment",  re.compile(r"\b(APARTMENT|APT BLDG|APT\.|MULTI-FAMILY|MULTIFAMILY|MFU|TOWNHOM|CONDO|HIGH-RISE|HIGH RISE|MID-RISE|LOFT)\b", re.I)),
    ("residential",re.compile(r"\b(RESIDENTIAL|SINGLE FAMILY|S\.F\. RES|SF RES|SFR|HOME|HOUSE|GARAGE|DRIVEWAY|FENCE|POOL|PATIO|DECK|SHED)\b", re.I)),
    ("commercial", re.compile(r"\b(COMMERCIAL|BUSINESS|MERCANTILE|TENANT FINISH|TENANT IMPROVEMENT)\b", re.I)),
    ("sign",       re.compile(r"\b(SIGN|SIGNAGE|BILLBOARD|ILLUM)\b", re.I)),
    ("infrastructure", re.compile(r"\b(WATER|WASTE WATER|WW UTILITY|SEWER|UTILITY|PAVING|ROADWAY|BRIDGE|DRAINAGE)\b", re.I)),
]


def classify(comments: str | None, permit_type: str | None) -> str | None:
    blob = " ".join(s for s in (comments, permit_type) if s)
    if not blob:
        return None
    for label, regex in RULES:
        if regex.search(blob):
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
