import re
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, computed_field

# Sources that carry their own permit valuation (City of Houston feeds).
# Anything else is a county/city feed where $ value + owner come from the
# appraisal roll, which lags new construction — so a missing value there
# means "not appraised yet", not "no data".
_COH_SOURCES = {"houston_ereport", "houston_sold_permits"}

# Permit-nature classification: distinguish a NEW BUILDING permit from the
# ancillary trade/site sub-permits that share the same project. Driven off
# permit_type (county PERMITNAME is descriptive) + comments (COH "Building
# Pmt" is generic, so the real signal — "NEW ... SHELL BLDG" — is in the
# project description). Order matters: trades/site checked before the
# generic building bucket so a "Fire Sprinkler" on a warehouse isn't a build.
_NATURE_RULES: list[tuple[str, re.Pattern]] = [
    ("sign",       re.compile(r"\bSIGN(S|AGE)?\b|BILLBOARD", re.I)),
    ("fire",       re.compile(r"\b(FIRE|SPRINKLER|ALARM|STANDPIPE|FIRE PUMP|FIRE LINE)\b", re.I)),
    ("site_civil", re.compile(r"\b(DRIVEWAY|PAVING|GRADING|STORM ?WATER|STORM SEWER|DETENTION|UTILITY|WATER LINE|SEWER|RIGHT OF WAY|SITE WORK|CIVIL SITE|IRRIGATION|SEWERAGE|OSSF|CULVERT)\b", re.I)),
    ("mep",        re.compile(r"\b(ELECTRIC|PLUMB|MECHANICAL|\bHVAC\b|BOILER|GENERATOR|SOLAR|GREASE)\b", re.I)),
    ("demolition", re.compile(r"\bDEMO(LITION)?\b", re.I)),
    ("remodel",    re.compile(r"\b(REMODEL|RENOVAT|TENANT|FINISH ?OUT|BUILD.?OUT|ALTERATION|REPAIR|RE-?ROOF|ADDITION)\b", re.I)),
    ("new_building", re.compile(r"\b(NEW (COMMERCIAL|SHELL|WAREHOUSE|BUILDING|BLDG|STRUCTURE|RESIDEN|HOME)|SHELL (BLDG|BUILDING)|HIGH.?PILE|GROUND ?UP|NEW \d|SF SHELL|TILT.?WALL)\b", re.I)),
    # Generic building permit — catches City-of-Houston "Building Pmt" and other
    # building/structure permits that don't carry a clear new-vs-remodel signal.
    # Last rule so the specific buckets above win first.
    ("building",   re.compile(r"\b(BUILDING PMT|BLDG PMT|OCC.?BLDG|MDI STRUCTURE|COMMERCIAL BUILDING|BUILDING PERMIT|NEW BLDG)\b", re.I)),
]

# permit_nature values that count as "building/structure work" (vs trade/site/
# sign permits) — used by the cross-source "Building" filter.
BUILDING_NATURES = ("new_building", "remodel", "building")


def classify_permit_nature(permit_type: Optional[str], comments: Optional[str]) -> Optional[str]:
    text = " ".join(filter(None, [permit_type or "", comments or ""]))
    if not text.strip():
        return None
    for label, rx in _NATURE_RULES:
        if rx.search(text):
            return label
    return None


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
    permit_nature: Optional[str] = None  # stored: new_building/remodel/building/fire/mep/site_civil/sign/demolition

    @computed_field
    @property
    def appraisal_status(self) -> Optional[str]:
        """For county/city-sourced permits: 'matched' once appraisal data is
        attached, else 'pending' (new build not on the appraisal roll yet).
        None for City-of-Houston permits, which carry their own valuation."""
        if not self.source or self.source in _COH_SOURCES:
            return None
        return "matched" if self.project_value is not None else "pending"

    @computed_field
    @property
    def use_class_assumed(self) -> bool:
        """True when use_class is an ASSUMPTION inferred from the project/owner
        name rather than structured data. County/city feeds have no structured
        use field, so any use_class on them is a name-based guess (show with an
        asterisk). City-of-Houston permits classify off a real scope
        description, so those are treated as confident."""
        if self.use_class is None:
            return False
        return bool(self.source) and self.source not in _COH_SOURCES

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
