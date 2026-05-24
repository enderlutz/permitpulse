"""Clean up builder names in the permits table.

Conservative cleanup — does NOT merge LLC/INC/CORP variants because that can
incorrectly collapse legitimately distinct entities (e.g. each D.R. Horton
sub-LLC is its own legal entity). Only handles obvious artifacts:

  * leading/trailing whitespace
  * leading asterisks (Houston ePermit's marker for commercial entities)
  * internal whitespace collapse
  * rows that are empty / pure punctuation after cleanup → NULL

Run from `backend/`:
    python -m scripts.normalize_builders            # dry-run, prints sample
    python -m scripts.normalize_builders --apply    # writes changes
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import update  # noqa: E402

from db import SessionLocal, engine  # noqa: E402
from models import Permit  # noqa: E402


LEADING_PUNCT_RE = re.compile(r"^[\*\s\.,]+")
TRAILING_PUNCT_RE = re.compile(r"[\*\s]+$")
WHITESPACE_RE = re.compile(r"\s+")
JUNK_ONLY_RE = re.compile(r"^[\*\s\.,\-_]*$")


def clean(name: str | None) -> str | None:
    if not name:
        return None
    s = LEADING_PUNCT_RE.sub("", name)
    s = TRAILING_PUNCT_RE.sub("", s)
    s = WHITESPACE_RE.sub(" ", s).strip()
    if not s or JUNK_ONLY_RE.match(s):
        return None
    return s


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Write changes (default is dry-run)")
    p.add_argument("--sample", type=int, default=20)
    args = p.parse_args()

    db = SessionLocal()
    try:
        rows = db.query(Permit.id, Permit.builder).filter(Permit.builder.isnot(None)).all()
        print(f"Examining {len(rows)} permits with non-null builder...")

        changes: list[tuple[int, str, str | None]] = []
        for r in rows:
            cleaned = clean(r.builder)
            if cleaned != r.builder:
                changes.append((r.id, r.builder, cleaned))

        print(f"Would change {len(changes)} rows")
        print()
        print(f"Sample (first {args.sample}):")
        for pid, before, after in changes[:args.sample]:
            print(f"  #{pid:>6}  {before!r}  →  {after!r}")

        if not args.apply:
            print()
            print("Dry-run complete. Re-run with --apply to write changes.")
            return

        print()
        print("Applying changes...")
        applied = 0
        for pid, _before, after in changes:
            db.execute(update(Permit).where(Permit.id == pid).values(builder=after))
            applied += 1
            if applied % 500 == 0:
                db.commit()
                print(f"  {applied}/{len(changes)} committed")
        db.commit()
        print(f"Applied {applied} updates.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
