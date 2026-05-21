# permit-pulse

Houston-area real-estate permit intelligence command center.

Map-first analytics with builder activity tracking, hotspot scoring, and opportunity discovery. Designed as a customizable workspace (ThinkOrSwim / VS Code lineage) with multiple pages tackling distinct decision problems for small-to-mid home builders.

## Stack

- **Frontend** — Vite + React + TypeScript + Tailwind + shadcn/ui + react-grid-layout + Leaflet + Recharts → Vercel
- **Backend** — FastAPI + SQLAlchemy → Railway (Dockerfile + railway.json)
- **DB** — Postgres (Supabase) with PostGIS for geo queries; falls back to SQLite locally via `DATABASE_URL` env var

## Run locally

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/ingest_archive.py        # downloads + parses Houston permit xlsx files
uvicorn main:app --reload --port 8090

# Frontend
cd frontend
npm install
npm run dev                              # http://localhost:5173
```

## Data sources

- Houston Public Works weekly Permit eReports (xlsx archive, 2017 → Nov 2025)
- Houston Sold Permits Search (3-year rolling, scraped for 2026+ data)
- Census Geocoder for lat/lng resolution

## Deployment

- Frontend → Vercel: `vercel deploy` from `frontend/`
- Backend → Railway: connects to `backend/` (Dockerfile auto-detected)
- DB → Supabase: set `DATABASE_URL` in both Railway + local `.env`
