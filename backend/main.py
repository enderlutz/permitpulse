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

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
