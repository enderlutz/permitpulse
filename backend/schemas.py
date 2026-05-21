from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class PermitOut(BaseModel):
    id: int
    project_no: str
    permit_date: Optional[date]
    permit_type: Optional[str]
    address: Optional[str]
    zip_code: Optional[str]
    comments: Optional[str]
    builder: Optional[str]
    project_value: Optional[float]
    square_feet: Optional[int]
    use_class: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]

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
