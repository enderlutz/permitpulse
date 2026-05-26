from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from db import get_db
from models import Permit
from schemas import KpiSummary, HotspotZip

router = APIRouter()

# All analytics queries are derived from data that only refreshes once a day
# (via the GitHub Actions cron). Tell browsers + any CDN in front of us to
# cache aggressively. stale-while-revalidate lets the dashboard render
# instantly from cache while we refresh in the background.
ANALYTICS_CACHE = "public, max-age=600, stale-while-revalidate=3600"


def _reference_date(db: Session) -> date:
    """Most-recent permit date in the DB — used as the 'now' anchor for periods.

    Anchoring on actual calendar today fails when working with an archived dataset
    (e.g., the Houston eReport series ended Nov 2025). Anchoring on the latest
    data point means '30 days' always refers to the freshest 30 days available.
    """
    latest = db.query(func.max(Permit.permit_date)).scalar()
    return latest or date.today()


def _date_range(period: str, db: Session) -> tuple[date, date, date]:
    """Return (start, prev_start, ref). Period: 7d, 30d, 90d, 12mo."""
    ref = _reference_date(db)
    if period.endswith("d"):
        days = int(period[:-1])
    elif period == "12mo":
        days = 365
    else:
        days = 30
    start = ref - timedelta(days=days)
    prev_start = start - timedelta(days=days)
    return start, prev_start, ref


@router.get("/kpis", response_model=KpiSummary)
def kpis(response: Response, db: Session = Depends(get_db), period: str = Query("30d")):
    response.headers["Cache-Control"] = ANALYTICS_CACHE
    start, prev_start, today = _date_range(period, db)

    this_period = db.query(func.count(Permit.id)).filter(Permit.permit_date >= start).scalar() or 0
    prev_period = (
        db.query(func.count(Permit.id))
        .filter(Permit.permit_date >= prev_start, Permit.permit_date < start)
        .scalar()
        or 0
    )
    velocity = ((this_period - prev_period) / prev_period * 100) if prev_period else 0.0

    top_zip_row = (
        db.query(Permit.zip_code, func.count(Permit.id).label("n"))
        .filter(Permit.permit_date >= start, Permit.zip_code.isnot(None))
        .group_by(Permit.zip_code)
        .order_by(func.count(Permit.id).desc())
        .first()
    )
    # Group on canonical_builder when available (collapses 5 D.R. Horton
    # variants into one) and fall back to raw builder for un-classified rows.
    builder_name_expr = func.coalesce(Permit.canonical_builder, Permit.builder).label("name")
    top_builder_row = (
        db.query(builder_name_expr, func.count(Permit.id).label("n"))
        .filter(Permit.permit_date >= start, Permit.builder.isnot(None))
        .group_by("name")
        .order_by(func.count(Permit.id).desc())
        .first()
    )

    hotspot_count = (
        db.query(Permit.zip_code)
        .filter(Permit.permit_date >= start)
        .group_by(Permit.zip_code)
        .having(func.count(Permit.id) >= 25)
        .count()
    )

    return KpiSummary(
        permits_this_period=this_period,
        permits_prev_period=prev_period,
        velocity_pct=round(velocity, 1),
        hotspot_count=hotspot_count,
        top_zip=top_zip_row[0] if top_zip_row else None,
        top_zip_count=top_zip_row[1] if top_zip_row else 0,
        top_builder=top_builder_row[0] if top_builder_row else None,
        top_builder_count=top_builder_row[1] if top_builder_row else 0,
    )


@router.get("/hotspots", response_model=list[HotspotZip])
def hotspots(
    response: Response,
    db: Session = Depends(get_db),
    period: str = Query("90d"),
    limit: int = Query(15),
):
    """Composite hotspot scoring per ZIP — volume + velocity + recency."""
    response.headers["Cache-Control"] = ANALYTICS_CACHE
    start, prev_start, today = _date_range(period, db)

    rows = (
        db.query(
            Permit.zip_code,
            func.count(Permit.id).label("n"),
        )
        .filter(Permit.permit_date >= start, Permit.zip_code.isnot(None))
        .group_by(Permit.zip_code)
        .order_by(func.count(Permit.id).desc())
        .limit(limit)
        .all()
    )

    # Per-zip velocity and 12-week sparkline
    out: list[HotspotZip] = []
    for zip_code, n in rows:
        prev = (
            db.query(func.count(Permit.id))
            .filter(
                Permit.zip_code == zip_code,
                Permit.permit_date >= prev_start,
                Permit.permit_date < start,
            )
            .scalar()
            or 0
        )
        velocity = ((n - prev) / prev * 100) if prev else 0.0

        # 12-week sparkline
        spark = []
        for w in range(11, -1, -1):
            w_end = today - timedelta(days=w * 7)
            w_start = w_end - timedelta(days=7)
            c = (
                db.query(func.count(Permit.id))
                .filter(
                    Permit.zip_code == zip_code,
                    Permit.permit_date >= w_start,
                    Permit.permit_date < w_end,
                )
                .scalar()
                or 0
            )
            spark.append(c)

        # Composite score: 60% volume rank, 30% velocity, 10% peak recency
        max_n = rows[0][1] if rows else 1
        vol_score = (n / max_n) * 60
        vel_score = max(min(velocity / 100, 1), -1) * 30
        rec_score = (spark[-1] / max(max(spark), 1)) * 10
        score = round(vol_score + vel_score + rec_score, 1)

        out.append(
            HotspotZip(
                zip_code=zip_code,
                permit_count=n,
                velocity_pct=round(velocity, 1),
                avg_value=None,
                score=score,
                sparkline=spark,
            )
        )
    return sorted(out, key=lambda x: x.score, reverse=True)


@router.get("/timeseries")
def timeseries(
    response: Response,
    db: Session = Depends(get_db),
    period: str = Query("12mo"),
    bucket: str = Query("week"),
    zip_code: Optional[str] = Query(None, alias="zip"),
):
    """Time-series volume for time-lapse scrubber and trend charts."""
    response.headers["Cache-Control"] = ANALYTICS_CACHE
    start, _, today = _date_range(period, db)
    q = db.query(Permit.permit_date, Permit.permit_type).filter(Permit.permit_date >= start)
    if zip_code:
        q = q.filter(Permit.zip_code == zip_code)
    rows = q.all()

    # Bucket in Python — small enough
    from collections import defaultdict

    buckets: dict[str, int] = defaultdict(int)
    for d, _t in rows:
        if not d:
            continue
        if bucket == "day":
            key = d.isoformat()
        elif bucket == "month":
            key = f"{d.year:04d}-{d.month:02d}"
        else:  # week
            iso = d.isocalendar()
            key = f"{iso.year}-W{iso.week:02d}"
        buckets[key] += 1
    return [{"bucket": k, "count": v} for k, v in sorted(buckets.items())]


@router.get("/type-mix")
def type_mix(response: Response, db: Session = Depends(get_db), period: str = Query("90d")):
    response.headers["Cache-Control"] = ANALYTICS_CACHE
    start, _, _ = _date_range(period, db)
    rows = (
        db.query(Permit.permit_type, func.count(Permit.id).label("n"))
        .filter(Permit.permit_date >= start, Permit.permit_type.isnot(None))
        .group_by(Permit.permit_type)
        .order_by(func.count(Permit.id).desc())
        .all()
    )
    return [{"type": t, "count": n} for t, n in rows]
