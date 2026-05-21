from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from db import get_db
from models import Permit

router = APIRouter()


def _reference_date(db: Session) -> date:
    return db.query(func.max(Permit.permit_date)).scalar() or date.today()


@router.get("/leaderboard")
def leaderboard(
    db: Session = Depends(get_db),
    period: str = Query("30d"),
    limit: int = Query(10),
):
    days = int(period[:-1]) if period.endswith("d") else (365 if period == "12mo" else 30)
    cutoff = _reference_date(db) - timedelta(days=days)

    rows = (
        db.query(Permit.builder, func.count(Permit.id).label("n"))
        .filter(Permit.permit_date >= cutoff, Permit.builder.isnot(None))
        .group_by(Permit.builder)
        .order_by(func.count(Permit.id).desc())
        .limit(limit)
        .all()
    )
    return [{"builder": b, "permit_count": n} for b, n in rows]


@router.get("/{builder}/footprint")
def builder_footprint(
    builder: str,
    db: Session = Depends(get_db),
    period: str = Query("90d"),
):
    days = int(period[:-1]) if period.endswith("d") else (365 if period == "12mo" else 90)
    cutoff = _reference_date(db) - timedelta(days=days)

    permits = (
        db.query(Permit)
        .filter(Permit.builder.ilike(f"%{builder}%"), Permit.permit_date >= cutoff)
        .all()
    )
    if not permits:
        raise HTTPException(404, "no permits for this builder in period")

    zip_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for p in permits:
        if p.zip_code:
            zip_counts[p.zip_code] = zip_counts.get(p.zip_code, 0) + 1
        if p.permit_type:
            type_counts[p.permit_type] = type_counts.get(p.permit_type, 0) + 1

    return {
        "builder": builder,
        "permit_count": len(permits),
        "zip_codes": sorted(zip_counts.items(), key=lambda x: -x[1])[:15],
        "permit_types": type_counts,
        "pins": [
            {"id": p.id, "lat": p.latitude, "lng": p.longitude, "address": p.address}
            for p in permits
            if p.latitude and p.longitude
        ][:500],
    }
