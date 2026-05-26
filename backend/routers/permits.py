from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, cast, Integer

from db import get_db
from models import Permit
from schemas import PermitOut

router = APIRouter()
CACHE = "public, max-age=600, stale-while-revalidate=3600"
META_CACHE = "public, max-age=120, stale-while-revalidate=600"  # meta refreshes more often


def _reference_date(db: Session) -> date:
    """Anchor period queries on the latest permit date — see analytics.py docstring."""
    return db.query(func.max(Permit.permit_date)).scalar() or date.today()


def _project_year_expr():
    """Year-of-permit derived from project_no prefix (YY in 'YYDDDxxx').

    permit_date in this DB is the scrape date, not the real issuance date
    (city site doesn't expose per-permit dates). Without this projection,
    re-scraping a 2025 project would file it under 2026 just because we
    scraped it today. Project number 25xxx ⇒ 2025; 26xxx ⇒ 2026.
    """
    yy = cast(func.substr(Permit.project_no, 1, 2), Integer)
    return 2000 + yy


def _period_days(period: str) -> int:
    if period.endswith("d"):
        return int(period[:-1])
    if period == "12mo":
        return 365
    return 30


@router.get("", response_model=list[PermitOut])
def list_permits(
    db: Session = Depends(get_db),
    zip_code: Optional[str] = Query(None, alias="zip"),
    permit_type: Optional[str] = Query(None),
    use_class: Optional[str] = Query(None, description="warehouse/retail/office/restaurant/apartment/residential"),
    builder: Optional[str] = Query(None),
    period: Optional[str] = Query(None, description="7d/30d/90d/12mo — anchored on latest permit date"),
    years: Optional[str] = Query(None, description="Comma-separated years to include, e.g. 2025,2026"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    has_geo: bool = Query(False, description="Only permits with lat/lng"),
    bbox: Optional[str] = Query(None, description="south,west,north,east"),
    limit: int = Query(500, le=5000),
    offset: int = Query(0, ge=0),
):
    """Filterable permit list — used by map widget and table widget."""
    q = db.query(Permit)

    if zip_code:
        q = q.filter(Permit.zip_code == zip_code)
    if permit_type:
        q = q.filter(Permit.permit_type == permit_type)
    if use_class:
        q = q.filter(Permit.use_class == use_class)
    if builder:
        q = q.filter(Permit.builder.ilike(f"%{builder}%"))
    if years:
        try:
            year_list = [int(y.strip()) for y in years.split(",") if y.strip()]
        except ValueError:
            raise HTTPException(400, "years must be comma-separated integers")
        if year_list:
            q = q.filter(_project_year_expr().in_(year_list))
    if period and not date_from:
        ref = _reference_date(db)
        date_from = ref - timedelta(days=_period_days(period))
    if date_from:
        q = q.filter(Permit.permit_date >= date_from)
    if date_to:
        q = q.filter(Permit.permit_date <= date_to)
    if has_geo:
        q = q.filter(Permit.latitude.isnot(None), Permit.longitude.isnot(None))
    if bbox:
        try:
            s, w, n, e = [float(x) for x in bbox.split(",")]
            q = q.filter(
                Permit.latitude.between(s, n),
                Permit.longitude.between(w, e),
            )
        except ValueError:
            raise HTTPException(400, "bbox must be 'south,west,north,east'")

    return q.order_by(Permit.permit_date.desc()).offset(offset).limit(limit).all()


@router.get("/recent", response_model=list[PermitOut])
def recent_permits(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, le=500),
):
    cutoff = _reference_date(db) - timedelta(days=days)
    return (
        db.query(Permit)
        .filter(Permit.permit_date >= cutoff)
        .order_by(Permit.permit_date.desc())
        .limit(limit)
        .all()
    )


@router.get("/types")
def permit_types(db: Session = Depends(get_db)):
    rows = (
        db.query(Permit.permit_type, func.count(Permit.id).label("n"))
        .filter(Permit.permit_type.isnot(None))
        .group_by(Permit.permit_type)
        .order_by(func.count(Permit.id).desc())
        .all()
    )
    return [{"type": t, "count": n} for t, n in rows]


@router.get("/years")
def permit_years(response: Response, db: Session = Depends(get_db)):
    """Permit count per year — drives the year-filter UI.

    Year is derived from the project_no prefix (25 → 2025, 26 → 2026),
    NOT from permit_date. permit_date is the scrape date, which would
    incorrectly file every re-scraped 2025 project under 2026.
    """
    response.headers["Cache-Control"] = CACHE
    yr_expr = _project_year_expr().label("yr")
    rows = (
        db.query(yr_expr, func.count(Permit.id).label("n"))
        .filter(Permit.project_no.isnot(None))
        .filter(func.length(Permit.project_no) >= 2)
        .group_by("yr")
        .order_by("yr")
        .all()
    )
    return [{"year": int(yr), "count": n} for yr, n in rows if yr is not None and 2000 <= yr <= 2030]


@router.get("/meta")
def permits_meta(response: Response, db: Session = Depends(get_db)):
    """Dataset freshness/coverage signals for the dashboard 'Last updated' badge."""
    response.headers["Cache-Control"] = META_CACHE
    latest_ingest = db.query(func.max(Permit.ingested_at)).scalar()
    latest_permit = db.query(func.max(Permit.permit_date)).scalar()
    total = db.query(func.count(Permit.id)).scalar() or 0
    geocoded = db.query(func.count(Permit.id)).filter(Permit.latitude.isnot(None)).scalar() or 0
    return {
        "latest_ingest": latest_ingest.isoformat() if latest_ingest else None,
        "latest_permit_date": latest_permit.isoformat() if latest_permit else None,
        "total": total,
        "geocoded": geocoded,
    }


@router.get("/{permit_id}", response_model=PermitOut)
def get_permit(permit_id: int, db: Session = Depends(get_db)):
    p = db.get(Permit, permit_id)
    if not p:
        raise HTTPException(404, "permit not found")
    return p
