from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from db import get_db
from models import Permit

router = APIRouter()


def _reference_date(db: Session) -> date:
    return db.query(func.max(Permit.permit_date)).scalar() or date.today()

# preset definitions used by the Opportunity Finder widget
PRESETS = {
    "small-builder-gap": {
        "name": "Small-Builder Gap",
        "description": "ZIPs with heavy big-builder activity but no small-builder presence.",
    },
    "commercial-residential-divergence": {
        "name": "Commercial > Residential",
        "description": "Areas where commercial permits are surging while residential lags — flip opportunity.",
    },
    "emerging-velocity": {
        "name": "Emerging Velocity",
        "description": "ZIPs with low absolute volume but rapidly accelerating permit count.",
    },
    "cooling-market": {
        "name": "Cooling Market (Risk Pulse)",
        "description": "Previously active ZIPs that are decelerating — avoid or revisit.",
    },
}


@router.get("/presets")
def list_presets():
    return [{"id": k, **v} for k, v in PRESETS.items()]


@router.get("/run/{preset_id}")
def run_preset(
    preset_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(10),
):
    today = _reference_date(db)
    p30 = today - timedelta(days=30)
    p90 = today - timedelta(days=90)
    p180 = today - timedelta(days=180)

    if preset_id == "small-builder-gap":
        # ZIPs ranked by big-builder presence where small-builder count is low
        BIG = ["D.R. HORTON", "PERRY HOMES", "K. HOVNANIAN", "LENNAR", "MERITAGE", "TOLL BROTHERS"]
        big_filter = func.upper(Permit.builder).in_(BIG)
        rows = (
            db.query(
                Permit.zip_code,
                func.sum(case((big_filter, 1), else_=0)).label("big"),
                func.sum(case((big_filter, 0), else_=1)).label("small"),
            )
            .filter(Permit.permit_date >= p90, Permit.zip_code.isnot(None))
            .group_by(Permit.zip_code)
            .having(func.sum(case((big_filter, 1), else_=0)) >= 5)
            .all()
        )
        scored = [
            {"zip_code": z, "big_builder_permits": b, "small_builder_permits": s, "score": b - s}
            for z, b, s in rows
        ]
        return sorted(scored, key=lambda x: x["score"], reverse=True)[:limit]

    if preset_id == "emerging-velocity":
        recent = dict(
            db.query(Permit.zip_code, func.count(Permit.id))
            .filter(Permit.permit_date >= p30, Permit.zip_code.isnot(None))
            .group_by(Permit.zip_code)
            .all()
        )
        prior = dict(
            db.query(Permit.zip_code, func.count(Permit.id))
            .filter(Permit.permit_date >= p90, Permit.permit_date < p30, Permit.zip_code.isnot(None))
            .group_by(Permit.zip_code)
            .all()
        )
        out = []
        for z, r in recent.items():
            p = prior.get(z, 0)
            if r < 3:
                continue
            velocity = ((r - p / 2) / max(p / 2, 1)) * 100 if p else 200.0
            out.append({"zip_code": z, "recent_30d": r, "prior_60d": p, "velocity_pct": round(velocity, 1)})
        return sorted(out, key=lambda x: x["velocity_pct"], reverse=True)[:limit]

    if preset_id == "cooling-market":
        recent = dict(
            db.query(Permit.zip_code, func.count(Permit.id))
            .filter(Permit.permit_date >= p30, Permit.zip_code.isnot(None))
            .group_by(Permit.zip_code)
            .all()
        )
        baseline = dict(
            db.query(Permit.zip_code, func.count(Permit.id))
            .filter(Permit.permit_date >= p180, Permit.permit_date < p30, Permit.zip_code.isnot(None))
            .group_by(Permit.zip_code)
            .all()
        )
        out = []
        for z, b in baseline.items():
            if b < 30:
                continue
            r = recent.get(z, 0)
            expected = b * (30 / 150)
            decel = ((r - expected) / expected) * 100 if expected else 0
            if decel < -20:
                out.append({"zip_code": z, "recent_30d": r, "expected": round(expected, 1), "decel_pct": round(decel, 1)})
        return sorted(out, key=lambda x: x["decel_pct"])[:limit]

    if preset_id == "commercial-residential-divergence":
        # heuristic: use permit_type and comments since we don't yet have firm use_class on every row
        rows = (
            db.query(
                Permit.zip_code,
                func.sum(case((Permit.permit_type.ilike("%commercial%"), 1), else_=0)).label("comm"),
                func.sum(case((Permit.use_class == "residential", 1), else_=0)).label("res"),
                func.count(Permit.id).label("total"),
            )
            .filter(Permit.permit_date >= p90, Permit.zip_code.isnot(None))
            .group_by(Permit.zip_code)
            .all()
        )
        out = []
        for z, c, r, t in rows:
            if t < 10:
                continue
            ratio = (c or 0) / max((r or 0) + 1, 1)
            if ratio > 0.4:
                out.append({"zip_code": z, "commercial": c, "residential": r, "ratio": round(ratio, 2)})
        return sorted(out, key=lambda x: x["ratio"], reverse=True)[:limit]

    return {"error": "unknown preset"}
