# Single-container image (frontend + API) for hosts like Render.
# Next.js listens on $PORT (public); FastAPI listens on 127.0.0.1:8000 (internal only).
FROM node:22-bookworm-slim AS web
WORKDIR /web
ENV NEXT_OUTPUT=standalone NEXT_TELEMETRY_DISABLED=1
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin fonts-dejavu-core libstdc++6 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=web /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=web /web/.next/standalone/ frontend/
COPY --from=web /web/.next/static frontend/.next/static
COPY --from=web /web/public frontend/public
COPY start.sh ./start.sh
RUN useradd -m appuser && mkdir -p /app/backend/.data && chown -R appuser /app
USER appuser
ENV NODE_ENV=production HOSTNAME=0.0.0.0 BACKEND_URL=http://127.0.0.1:8000 NEXT_TELEMETRY_DISABLED=1
EXPOSE 10000
CMD ["sh", "/app/start.sh"]
