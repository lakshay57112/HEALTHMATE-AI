from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import account, assistant, auth, documents, family, health, medicines, notifications, nutrition, profile, reports
from app.core.config import get_settings

settings = get_settings()


class PrivacyFilter(logging.Filter):
    """Belt-and-braces: never let request bodies or tokens reach logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage())
        return "Bearer " not in msg and "password" not in msg.lower()


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for h in logging.getLogger().handlers:
    h.addFilter(PrivacyFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if settings.reminder_engine_enabled and settings.environment != "test":
        from app.services.reminder_engine import run_forever

        task = asyncio.create_task(run_forever())
    yield
    if task:
        task.cancel()


app = FastAPI(title="HealthMate AI API", version="1.0.0", lifespan=lifespan,
              description="Backend for HealthMate AI — document intelligence, medicine management, nutrition, caregivers and an agentic assistant.",
              docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url="/api/redoc")

app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Content-Security-Policy", "frame-ancestors 'self'")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.path.startswith("/api/") and "cache-control" not in resp.headers:
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(x) for x in e["loc"][1:]) or "body", "message": e["msg"].replace("Value error, ", "")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors[0]["message"] if errors else "Invalid input", "errors": errors})


for r in (auth, profile, documents, reports, medicines, nutrition, health, family, notifications, assistant, account):
    app.include_router(r.router, prefix=settings.api_prefix)


@app.get("/api/health")
def healthcheck():
    return {"status": "ok"}
