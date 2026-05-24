"""Quick end-to-end test of the composite-key upsert path against Supabase.
Uses a clearly-fake project_no so it can be safely deleted after.

Run from `backend/`:
    python -m scripts.test_upsert
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date  # noqa: E402

from sqlalchemy import text  # noqa: E402

from db import engine  # noqa: E402
from scripts.scrape_sold_permits import upsert_rows  # noqa: E402


TEST_PN = "TESTUPSERT00"


def main():
    print(f"=== Testing composite-key upsert with project_no={TEST_PN} ===")

    # Clean up any leftover from prior runs
    with engine.begin() as conn:
        n = conn.execute(text("DELETE FROM permits WHERE project_no = :pn"),
                         {"pn": TEST_PN}).rowcount
        print(f"  Cleaned {n} pre-existing rows")

    # Seed a LEGACY row, simulating pre-migration data
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO permits (project_no, permit_code, permit_date, "
            "permit_type, address, source) VALUES "
            "(:pn, 'LEGACY', :d, 'Building Pmt', '123 TEST ST', 'test')"
        ), {"pn": TEST_PN, "d": date.today()})
        print(f"  Seeded 1 LEGACY row")

    # Verify
    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT project_no, permit_code, permit_type FROM permits "
            "WHERE project_no = :pn ORDER BY id"
        ), {"pn": TEST_PN}).fetchall()
        print(f"  Before upsert: {[(r[0], r[1], r[2]) for r in rows]}")

    # Now call the REAL upsert function with 3 sub-permits
    fake_rows = [
        {"project_no": TEST_PN, "permit_code": "BL",
         "permit_date": date.today(), "permit_type": "Building Pmt",
         "address": "123 TEST ST", "zip_code": "77019",
         "comments": "test building", "builder": "TEST BUILDER LLC",
         "project_value": 100000.0, "source": "test"},
        {"project_no": TEST_PN, "permit_code": "EL",
         "permit_date": date.today(), "permit_type": "Electrical Pmt",
         "address": "123 TEST ST", "zip_code": "77019",
         "comments": "test electrical", "builder": "TEST BUILDER LLC",
         "project_value": 5000.0, "source": "test"},
        {"project_no": TEST_PN, "permit_code": "PL",
         "permit_date": date.today(), "permit_type": "Plumbing Pmt",
         "address": "123 TEST ST", "zip_code": "77019",
         "comments": "test plumbing", "builder": "TEST BUILDER LLC",
         "project_value": 3000.0, "source": "test"},
    ]

    print()
    print("Calling upsert_rows() with 3 sub-permits...")
    try:
        n = upsert_rows(fake_rows)
        print(f"  upsert_rows returned: {n}")
    except Exception as e:
        print(f"  ❌ EXCEPTION: {type(e).__name__}: {e}")
        return

    # Verify state
    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT project_no, permit_code, permit_type, project_value "
            "FROM permits WHERE project_no = :pn ORDER BY permit_code"
        ), {"pn": TEST_PN}).fetchall()
        print(f"  After upsert: {len(rows)} rows")
        for r in rows:
            print(f"    {r[0]}  code={r[1]}  type={r[2]}  value={r[3]}")

    # Expected: 3 rows (BL, EL, PL) and NO LEGACY row
    codes = sorted([r[1] for r in rows])
    if codes == ["BL", "EL", "PL"]:
        print()
        print("  ✅ PASS — LEGACY deleted, 3 sub-permits inserted with correct codes")
    elif "LEGACY" in codes:
        print()
        print("  ❌ FAIL — LEGACY row was NOT deleted")
    else:
        print()
        print(f"  ⚠️  UNEXPECTED — got codes {codes}")

    # Re-run upsert (idempotency check)
    print()
    print("Calling upsert_rows() AGAIN with same rows (idempotency)...")
    try:
        n = upsert_rows(fake_rows)
        print(f"  Returned: {n}")
    except Exception as e:
        print(f"  ❌ EXCEPTION: {type(e).__name__}: {e}")
        return

    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT permit_code FROM permits WHERE project_no = :pn ORDER BY permit_code"
        ), {"pn": TEST_PN}).fetchall()
        codes = sorted([r[0] for r in rows])
        if codes == ["BL", "EL", "PL"]:
            print(f"  ✅ Idempotent — still 3 rows after re-upsert")
        else:
            print(f"  ❌ Got {len(rows)} rows: {codes}")

    # Cleanup
    with engine.begin() as conn:
        n = conn.execute(text("DELETE FROM permits WHERE project_no = :pn"),
                         {"pn": TEST_PN}).rowcount
        print(f"\n  Cleanup: deleted {n} test rows")


if __name__ == "__main__":
    main()
