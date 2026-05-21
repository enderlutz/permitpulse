from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Index, Text
from sqlalchemy.sql import func
from db import Base


class Permit(Base):
    __tablename__ = "permits"

    id = Column(Integer, primary_key=True, index=True)
    project_no = Column(String, unique=True, index=True)
    permit_date = Column(Date, index=True)
    permit_type = Column(String, index=True)
    address = Column(String, index=True)
    zip_code = Column(String, index=True)
    comments = Column(Text)

    # enrichment
    builder = Column(String, index=True, nullable=True)
    project_value = Column(Float, nullable=True)
    square_feet = Column(Integer, nullable=True)
    use_class = Column(String, nullable=True)  # residential/commercial/warehouse/retail
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    source = Column(String, default="houston_ereport")
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_permit_lat_lng", "latitude", "longitude"),
        Index("ix_permit_zip_date", "zip_code", "permit_date"),
    )


class Builder(Base):
    __tablename__ = "builders"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String, unique=True, index=True)
    aliases = Column(Text)  # JSON array of alternate spellings
    is_public_traded = Column(Integer, default=0)
    tier = Column(String, nullable=True)  # major/mid/small
    color = Column(String, nullable=True)  # hex color for map
