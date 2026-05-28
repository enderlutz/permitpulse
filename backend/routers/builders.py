from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_

from db import get_db
from models import Permit

router = APIRouter()

VALID_TIERS = {"national", "local", "individual", "unknown"}
CACHE = "public, max-age=600, stale-while-revalidate=3600"


def _reference_date(db: Session) -> date:
    return db.query(func.max(Permit.permit_date)).scalar() or date.today()


def _parse_tiers(tiers: Optional[str]) -> list[str]:
    """Parse comma-separated ?tiers=national,local,individual into a list.
    Default: all three real tiers (national + local + individual). Homeowner
    permits aren't noise — they're a remodel-demand signal and surface
    subcontracting opportunities for builders."""
    if not tiers:
        return ["national", "local", "individual"]
    parts = [t.strip().lower() for t in tiers.split(",") if t.strip()]
    return [t for t in parts if t in VALID_TIERS] or ["national", "local", "individual"]


@router.get("/leaderboard")
def leaderboard(
    response: Response,
    db: Session = Depends(get_db),
    period: str = Query("30d"),
    limit: int = Query(10),
    tiers: Optional[str] = Query(None, description="Comma-separated: national,local,individual,unknown. Default: national,local"),
):
    response.headers["Cache-Control"] = CACHE
    days = int(period[:-1]) if period.endswith("d") else (365 if period == "12mo" else 30)
    cutoff = _reference_date(db) - timedelta(days=days)
    tier_filter = _parse_tiers(tiers)

    # Group by canonical_builder when available (collapses national name variants
    # like 'D.R. HORTON - TEXAS, LTD' into 'D.R. Horton') and fall back to the
    # raw builder name for rows that haven't been classified yet.
    name_col = func.coalesce(Permit.canonical_builder, Permit.builder).label("name")

    rows = (
        db.query(
            name_col,
            func.count(Permit.id).label("n"),
            func.max(Permit.builder_type).label("tier"),
        )
        .filter(
            Permit.permit_date >= cutoff,
            Permit.builder.isnot(None),
            or_(
                Permit.builder_type.in_(tier_filter),
                # Rows not yet classified default-in only when 'local' is requested
                # (the most permissive bucket) so the leaderboard isn't empty on a
                # fresh DB before classifier runs.
                Permit.builder_type.is_(None) if "local" in tier_filter else False,
            ),
        )
        .group_by("name")
        .order_by(func.count(Permit.id).desc())
        .limit(limit)
        .all()
    )
    return [
        {"builder": name, "permit_count": n, "tier": tier}
        for name, n, tier in rows
    ]


@router.get("/{builder}/footprint")
def builder_footprint(
    builder: str,
    response: Response,
    db: Session = Depends(get_db),
    period: str = Query("90d"),
):
    """Per-builder detail view: aggregate stats + pins for the map +
    monthly volume trend + a slice of recent permits.

    Matches on canonical_builder first when the name is one of our recognized
    canonicals (so a click on "D.R. Horton" pulls every entity variant);
    otherwise falls back to ILIKE on the raw builder name so a click on
    a freeform name like "BECKLEY COMMUNITY LLC" still works.
    """
    response.headers["Cache-Control"] = CACHE
    days = int(period[:-1]) if period.endswith("d") else (365 if period == "12mo" else 90)
    cutoff = _reference_date(db) - timedelta(days=days)

    # canonical_builder is the deduplicated display name; querying by it
    # collapses all entity variants. Fall back to raw builder ILIKE for any
    # name that isn't (yet) a canonical entry.
    canonical_match = (
        db.query(Permit.id)
        .filter(Permit.canonical_builder == builder)
        .limit(1)
        .first()
    )
    if canonical_match:
        q = db.query(Permit).filter(Permit.canonical_builder == builder)
    else:
        q = db.query(Permit).filter(Permit.builder.ilike(f"%{builder}%"))

    permits = q.filter(Permit.permit_date >= cutoff).all()
    if not permits:
        raise HTTPException(404, "no permits for this builder in period")

    zip_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    use_counts: dict[str, int] = {}
    total_value = 0.0
    valued_count = 0
    monthly: dict[str, int] = {}
    for p in permits:
        if p.zip_code:
            zip_counts[p.zip_code] = zip_counts.get(p.zip_code, 0) + 1
        if p.permit_type:
            type_counts[p.permit_type] = type_counts.get(p.permit_type, 0) + 1
        if p.use_class:
            use_counts[p.use_class] = use_counts.get(p.use_class, 0) + 1
        if p.project_value:
            total_value += float(p.project_value)
            valued_count += 1
        if p.permit_date:
            mk = f"{p.permit_date.year:04d}-{p.permit_date.month:02d}"
            monthly[mk] = monthly.get(mk, 0) + 1

    recent = sorted(
        [p for p in permits if p.permit_date is not None],
        key=lambda p: p.permit_date,
        reverse=True,
    )[:15]

    return {
        "builder": builder,
        "permit_count": len(permits),
        "total_value": round(total_value, 2),
        "valued_count": valued_count,
        "zip_codes": sorted(zip_counts.items(), key=lambda x: -x[1])[:15],
        "permit_types": sorted(type_counts.items(), key=lambda x: -x[1])[:10],
        "use_classes": sorted(use_counts.items(), key=lambda x: -x[1]),
        "monthly_trend": [
            {"month": m, "count": c} for m, c in sorted(monthly.items())
        ],
        "recent_permits": [
            {
                "id": p.id,
                "permit_date": p.permit_date.isoformat() if p.permit_date else None,
                "address": p.address,
                "zip_code": p.zip_code,
                "permit_type": p.permit_type,
                "project_value": p.project_value,
            }
            for p in recent
        ],
        "pins": [
            {
                "id": p.id,
                "lat": p.latitude,
                "lng": p.longitude,
                "address": p.address,
                "permit_date": p.permit_date.isoformat() if p.permit_date else None,
            }
            for p in permits
            if p.latitude and p.longitude
        ][:500],
    }
