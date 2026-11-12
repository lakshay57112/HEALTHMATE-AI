# Architecture

```
Browser (Next.js 14, React, Tailwind)                         FastAPI (Python 3.13)                       PostgreSQL 16
┌───────────────────────────────┐   /api/* rewrite   ┌──────────────────────────────────────┐   SQLAlchemy  ┌───────────┐
│ Patient app · Caregiver app   │ ─────────────────▶ │ Routers (auth, documents, reports,   │ ────────────▶ │ 28 tables │
│ AG-UI chat (SSE)              │ ◀── SSE events ─── │ medicines, nutrition, family, …)     │               └───────────┘
│ Reminder agent (TTS, notifs)  │                    │                                      │
│ Service worker (Web Push)     │ ◀── Web Push ───── │ Reminder engine (asyncio, every 60s) │──▶ pywebpush (VAPID)
└───────────────────────────────┘                    │ Document pipeline (background task)  │──▶ Tesseract / pypdf
                                                     │ Agent harness (ReAct + hooks)        │──▶ OpenAI | Gemini | demo
MCP clients (Claude Desktop…) ── stdio ──▶ mcp_server.py ──▶ REST API (Bearer token)       │──▶ Encrypted file store
                                                     └──────────────────────────────────────┘
```

## Document flow (Upload once → understand everything)
1. `POST /documents` — magic-byte check → encrypted storage → `MedicalDocument(status=uploaded)` → background `process_document`.
2. Pipeline nodes persist progress into `pipeline_steps` (the UI polls and shows live status).
3. Result stored as `extraction = {type, data, review{items, flags, field_confidence, overall_confidence, duplicates}}`, status `needs_review`.
4. Patient edits/confirms → `POST /documents/{id}/confirm` → `commit_document` re-validates and writes:
   - lab report → `MedicalReport` + `ReportParameter` (+ bilingual summary, fasting glucose → `HealthMeasurement`, RAG fact chunks)
   - prescription → `Prescription` + `PrescriptionMedicine` + deterministic `MedicineSchedule` (+ optional follow-up `Appointment`, optional replacement of renewed medicines)
   - diet advice / consultation → doctor instructions on the profile → nutrition plan regenerated (+ appointment records)
   - appointment → `Appointment`
   - always → raw OCR text indexed for RAG (flagged if injection was detected) + in-app notification.

## Reminder engine
Each tick, per patient: compute today's doses (`scheduling.doses_for_day`, applying the meal-delay rule and ignoring doses that were already past when a schedule was created) → due → notification + push (repeats per settings) → past the escalation window → mark missed, notify patient and permitted caregivers → refill / appointment / 21:00 daily summary. All idempotent via `Notification.dedupe_key`.

## Data model (main tables)
`users`, `patient_profiles`, `caregiver_connections`, `consent_records`, `medical_documents`, `document_chunks`, `medical_reports`, `report_parameters`, `prescriptions`, `prescription_medicines`, `medicine_schedules`, `medicine_logs`, `reminder_settings`, `meal_schedules`, `meal_logs`, `food_recommendations`, `nutrition_plans`, `appointments`, `health_measurements`, `daily_checkins`, `notifications`, `push_subscriptions`, `audit_logs`, `chat_messages`, `agent_memories`, `agent_proposals`, `agent_traces`, `llm_cache`.

## Frontend structure
- `/` landing, `/login`, `/register`, `/onboarding`, `/invite/[token]`
- `/app/*` patient app (auth guard + onboarding guard in `app/app/layout.tsx`), `/caregiver` caregiver app
- Data fetching: `useApi(path)` hook; uploads via XHR for real progress; assistant via `streamChat` SSE parser
- i18n: dictionary-based EN/HI for UI chrome; report explanations, reminders and assistant answers are bilingual from the backend
