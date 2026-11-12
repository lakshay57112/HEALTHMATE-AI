#!/bin/sh
# Starts the API (internal) and the Next.js server (public) in one container.
set -e
cd /app/backend
alembic upgrade head
python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers &
API_PID=$!
cd /app/frontend
PORT="${PORT:-10000}" node server.js &
WEB_PID=$!
# If either process exits, stop the container so the host restarts it.
while kill -0 "$API_PID" 2>/dev/null && kill -0 "$WEB_PID" 2>/dev/null; do sleep 5; done
exit 1
