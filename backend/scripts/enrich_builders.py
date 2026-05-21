"""Enrich permits with builder/contractor name by scraping the Houston Permit Portal.

Looks up each permit by Project No against permits.houstontx.gov.

NOTE: This is a Phase-2 deliverable for the client. For tonight's demo, run with --sample
to enrich a few hundred high-value permits so flagship pins show real builder names.
"""
import argparse
import sys
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SessionLocal  # noqa: E402
from models import Permit  # noqa: E402


PORTAL_BASE = "https://permits.houstontx.gov"


def scrape_one(client: httpx.Client, project_no: str) -> str | None:
    """Returns builder/contractor name if found, else None.

    This is a best-effort scraper — the portal is ASP.NET with postbacks, so the
    selectors here are placeholders that need to be calibrated against the live
    site once we have network access. Tonight's demo uses a curated builder list
    seeded by `seed_builders.py` rather than relying on this scraper.
    """
    try:
        r = client.get(f"{PORTAL_BASE}/PublicSearch.aspx?projno={project_no}", timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        # placeholder selector — update once portal is reachable
        cell = soup.find("td", {"id": "ContractorName"})
        return cell.get_text(strip=True) if cell else None
    except Exception:
        return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sample", type=int, default=100, help="how many permits to enrich")
    args = p.parse_args()

    db = SessionLocal()
    try:
        pending = (
            db.query(Permit)
            .filter(Permit.builder.is_(None), Permit.project_no.isnot(None))
            .order_by(Permit.permit_date.desc())
            .limit(args.sample)
            .all()
        )
        print(f"Attempting to enrich {len(pending)} permits with builder name")
        with httpx.Client(headers={"User-Agent": "permit-pulse/0.1"}) as client:
            for i, permit in enumerate(pending):
                name = scrape_one(client, permit.project_no)
                if name:
                    permit.builder = name
                if i % 20 == 0:
                    db.commit()
                time.sleep(0.4)  # be polite
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
