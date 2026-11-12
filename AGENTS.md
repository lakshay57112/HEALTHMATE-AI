# AGENTS.md — instructions for coding agents working on HealthMate AI

## Setup
- Backend: `cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && alembic upgrade head && python -m app.seed`
- Frontend: `cd frontend && npm install`
- Run: `uvicorn app.main:app --reload --port 8000` and `npm run dev` (Next proxies `/api/*` to the backend).

## Checks before you finish
1. `cd backend && pytest -q` — must pass (uses the `healthmate_test` PostgreSQL DB).
2. `python -m evals.run_evals` — every suite must meet its threshold in `evals/cases.json`.
3. `cd frontend && npm run typecheck && npm run build`.
4. If you touched UI flows: `python e2e/journeys.py` with both servers running.

## Non-negotiable safety rules (enforced in code — keep them that way)
- Never let an LLM output reach medicines, reports, appointments or nutrition without patient verification (`services/extraction/commit.py` is the only writer).
- Medicine schedules and notifications are deterministic (`services/scheduling.py`, `services/reminder_engine.py`). Do not add LLM calls there.
- Reference ranges come only from the document. `reports.compute_status` must stay range-only; never add default ranges.
- No agent tool may have `external=True`. New write tools must be `writes=True` (they are auto-gated by taint + HITL).
- Caregiver data access must go through `consent.connection_allows` (active connection + permission flag + latest consent).
- Logs and traces must not contain medical content (`observability.redact`, `audit._FORBIDDEN_META_KEYS`).

## Conventions
- Python: typed, Pydantic for all inputs, SQLAlchemy 2 style. Sensitive free text uses `EncryptedText` / `EncryptedJSON`.
- Schema changes: edit `app/models/models.py`, then `alembic revision --autogenerate -m "..."` and review the file.
- Frontend: client components with `useApi`; UI primitives in `src/components/ui`; user-facing strings go through `useI18n().t` where translated.
- Every new effect must use a block body — `useEffect(() => { … })` — never return an expression (Chrome's `scrollIntoView` returns a Promise).
- Accessibility: wrap inputs in `<Field label=…>` (auto-links label/hint/error), keep touch targets ≥ 44 px.
- New guardrail or extraction behaviour → add a case to `evals/cases.json`.
