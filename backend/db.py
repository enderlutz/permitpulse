import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./permit_pulse.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Pool tuning for production: the dashboard fires ~12-15 parallel requests
# on every page load (KPIs, leaderboard, map, hotspots, time-series, etc.).
# Default SQLAlchemy QueuePool is size=5, max_overflow=10 — easy to exhaust
# when a single user clicks around quickly, causing 500 errors that the
# browser then mis-reports as "CORS blocked" (FastAPI's CORS middleware
# can't add headers to a response Railway's edge has already replaced with
# its own 500 page).
#
# Postgres-side: Supabase Session pooler accepts up to ~60 connections per
# project on the free tier. Pool size 20 + overflow 30 = 50 max, well under
# the cap. recycle=300 closes idle connections before Supabase does so we
# don't hit "connection invalidated" errors on next checkout.
_pool_kwargs = {}
if not DATABASE_URL.startswith("sqlite"):
    _pool_kwargs.update(
        pool_size=20,
        max_overflow=30,
        pool_recycle=300,
        pool_timeout=10,
    )

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    **_pool_kwargs,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
