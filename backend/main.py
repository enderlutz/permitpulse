import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from db import engine, Base
from routers import permits, analytics, builders, opportunities

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="permit-pulse API",
    description="Houston permit intelligence backend",
    version="0.1.0",
    lifespan=lifespan,
)

# Hardcoded baseline — local dev + the production Vercel URL — so the API
# never breaks in browsers because of an unset env var (production CORS
# blocker discovered 2026-05-26). CORS_ORIGINS env var (comma-separated)
# extends this list if needed (e.g. for a custom domain later).
# allow_origin_regex matches any *.vercel.app subdomain so preview deploys
# don't need manual whitelisting.
_default_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "https://permitpulse-five.vercel.app",
]
_extra = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
origins = list(dict.fromkeys(_default_origins + _extra))  # dedupe, preserve order

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(permits.router, prefix="/api/permits", tags=["permits"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(builders.router, prefix="/api/builders", tags=["builders"])
app.include_router(opportunities.router, prefix="/api/opportunities", tags=["opportunities"])


@app.get("/")
def root():
    return {"app": "permit-pulse", "version": "0.1.0", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}
