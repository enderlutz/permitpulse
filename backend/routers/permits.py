from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from db import get_db
from models import Permit
from schemas import PermitOut

router = APIRouter()


def _reference_date(db: Session) -> date:
    """Anchor period queries on the latest permit date — see analytics.py docstring."""
    return db.query(func.max(Permit.permit_date)).scalar() or date.today()


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
            from sqlalchemy import extract
            q = q.filter(extract("year", Permit.permit_date).in_(year_list))
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
def permit_years(db: Session = Depends(get_db)):
    """Permit count per year — drives the year-filter UI."""
    from sqlalchemy import extract
    rows = (
        db.query(extract("year", Permit.permit_date).label("yr"), func.count(Permit.id).label("n"))
        .filter(Permit.permit_date.isnot(None))
        .group_by("yr")
        .order_by("yr")
        .all()
    )
    return [{"year": int(yr), "count": n} for yr, n in rows if yr is not None]


@router.get("/{permit_id}", response_model=PermitOut)
def get_permit(permit_id: int, db: Session = Depends(get_db)):
    p = db.get(Permit, permit_id)
    if not p:
        raise HTTPException(404, "permit not found")
    return p
