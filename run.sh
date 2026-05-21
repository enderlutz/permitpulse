#!/usr/bin/env bash
# Convenience launcher for local dev: backend on :8000, frontend on :5173.
set -e
cd "$(dirname "$0")"

(cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8090) &
BACK_PID=$!
trap "kill $BACK_PID 2>/dev/null" EXIT

(cd frontend && npm run dev) &
FRONT_PID=$!
trap "kill $BACK_PID $FRONT_PID 2>/dev/null" EXIT

wait
