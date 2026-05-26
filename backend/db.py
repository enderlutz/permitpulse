import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./permit_pulse.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Pool strategy: NullPool for Postgres (Supabase).
#
# Supabase's free-tier Session pooler (port 5432) has a low per-project
# connection cap and rejects bursts. SQLAlchemy's default QueuePool holds
# connections open across requests, which trips Supabase's limit during
# dashboard load (12-15 parallel requests from a single user). The previous
# attempt to *raise* pool_size made things worse: more idle conns held =
# more rejections from Supabase.
#
# NullPool opens a fresh connection per checkout and closes it immediately.
# Supabase's own pgbouncer handles efficient pooling on the DB side. Result:
# bursts go through cleanly because Supabase only sees in-flight conns, not
# idle ones we're holding for "maybe later".
_pool_kwargs = {}
if not DATABASE_URL.startswith("sqlite"):
    _pool_kwargs["poolclass"] = NullPool

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
