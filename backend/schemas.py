from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, computed_field

# Sources that carry their own permit valuation (City of Houston feeds).
# Anything else is a county/city feed where $ value + owner come from the
# appraisal roll, which lags new construction — so a missing value there
# means "not appraised yet", not "no data".
_COH_SOURCES = {"houston_ereport", "houston_sold_permits"}


class PermitOut(BaseModel):
    id: int
    project_no: str
    permit_code: Optional[str] = None
    permit_date: Optional[date]
    permit_type: Optional[str]
    address: Optional[str]
    zip_code: Optional[str]
    comments: Optional[str]
    builder: Optional[str]
    canonical_builder: Optional[str] = None
    builder_type: Optional[str] = None
    project_value: Optional[float]
    square_feet: Optional[int]
    use_class: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    source: Optional[str] = None

    @computed_field
    @property
    def appraisal_status(self) -> Optional[str]:
        """For county/city-sourced permits: 'matched' once appraisal data is
        attached, else 'pending' (new build not on the appraisal roll yet).
        None for City-of-Houston permits, which carry their own valuation."""
        if not self.source or self.source in _COH_SOURCES:
            return None
        return "matched" if self.project_value is not None else "pending"

    class Config:
        from_attributes = True


class HotspotZip(BaseModel):
    zip_code: str
    permit_count: int
    velocity_pct: float       # % change vs prior period
    avg_value: Optional[float]
    score: float              # composite 0-100
    sparkline: list[int]      # last 12 weeks of counts


class BuilderActivity(BaseModel):
    builder: str
    permit_count: int
    zip_codes: list[str]
    permit_types: dict[str, int]
    velocity_pct: float


class KpiSummary(BaseModel):
    permits_this_period: int
    permits_prev_period: int
    velocity_pct: float
    hotspot_count: int
    top_zip: Optional[str]
    top_zip_count: int
    top_builder: Optional[str]
    top_builder_count: int
