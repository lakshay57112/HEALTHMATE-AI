# HealthMate AI — REST API

Base URL: `/api` (proxied by the Next.js app). Interactive docs: `/api/docs` (Swagger) and `/api/redoc`.

Auth: HTTP-only session cookie `hm_session` set by `/auth/login`, `/auth/register` or `/auth/demo`; or `Authorization: Bearer <token>` (from `POST /auth/token`).
Errors: `{"detail": "human readable message", "errors"?: [{field, message}]}` with 4xx/5xx status.

## Account

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/account/audit` | Audit Log |
| `POST` | `/api/account/delete` | Delete Account |
| `GET` | `/api/account/export` | Export |
| `GET` | `/api/dashboard` | Dashboard |
| `GET` | `/api/system/status` | System Status |

## Assistant

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/assistant/chat` | Streams AG-UI events as Server-Sent Events. |
| `GET` | `/api/assistant/memory` | Memory |
| `DELETE` | `/api/assistant/memory/{mid}` | Forget |
| `POST` | `/api/assistant/proposals/{pid}/{decision}` | Human-in-the-loop: the only path by which an agent proposal changes data. |
| `GET` | `/api/assistant/sessions` | Sessions |
| `DELETE` | `/api/assistant/sessions/{sid}` | Delete Session |
| `GET` | `/api/assistant/sessions/{sid}/messages` | Session Messages |
| `GET` | `/api/assistant/status` | Status |
| `GET` | `/api/assistant/traces` | Traces |
| `GET` | `/api/assistant/traces/{tid}` | Trace Detail |

## Auth

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/demo` | Signs into the seeded demo account (sample data, clearly labelled). |
| `POST` | `/api/auth/login` | Login |
| `POST` | `/api/auth/logout` | Logout |
| `GET` | `/api/auth/me` | Me |
| `POST` | `/api/auth/register` | Register |
| `POST` | `/api/auth/token` | Bearer token for API clients such as the MCP server (same lifetime as the session). |

## Documents

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/documents` | List Documents |
| `POST` | `/api/documents` | Upload |
| `GET` | `/api/documents/samples` | List Samples |
| `POST` | `/api/documents/samples/{key}` | Upload Sample |
| `DELETE` | `/api/documents/{doc_id}` | Delete Document |
| `GET` | `/api/documents/{doc_id}` | Get Document |
| `POST` | `/api/documents/{doc_id}/confirm` | Confirm |
| `GET` | `/api/documents/{doc_id}/file` | Get File |
| `GET` | `/api/documents/{doc_id}/preview` | First-page PNG preview — works in every browser (iOS Safari and headless included), unlike embedded PDFs. |
| `POST` | `/api/documents/{doc_id}/reject` | Reject |
| `POST` | `/api/documents/{doc_id}/reprocess` | Reprocess |

## Family

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/caregiver/patients` | My Patients |
| `GET` | `/api/caregiver/patients/{patient_id}/summary` | Patient Summary |
| `GET` | `/api/family` | List Family |
| `POST` | `/api/family/invite` | Invite |
| `DELETE` | `/api/family/{cid}` | Revoke |
| `PUT` | `/api/family/{cid}/permissions` | Update Permissions |
| `POST` | `/api/family/{cid}/resend` | Resend |
| `GET` | `/api/invitations/{token}` | Invitation Info |
| `POST` | `/api/invitations/{token}/accept` | Accept |

## Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/appointments` | List Appointments |
| `POST` | `/api/appointments` | Create Appointment |
| `DELETE` | `/api/appointments/{appt_id}` | Delete Appointment |
| `PUT` | `/api/appointments/{appt_id}` | Update Appointment |
| `POST` | `/api/checkins` | Checkin |
| `GET` | `/api/checkins/today` | Checkin Today |
| `GET` | `/api/measurements` | List Measurements |
| `POST` | `/api/measurements` | Add Measurement |
| `GET` | `/api/measurements/latest` | Latest |
| `DELETE` | `/api/measurements/{mid}` | Delete Measurement |
| `GET` | `/api/timeline` | Timeline |

## Medicines

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/meals/log` | Log Meal |
| `GET` | `/api/meals/schedule` | Meal Schedule |
| `PUT` | `/api/meals/schedule` | Update Meals |
| `GET` | `/api/meals/today` | Meals Today |
| `GET` | `/api/medicines` | List Medicines |
| `POST` | `/api/medicines` | Add Medicine |
| `GET` | `/api/medicines/adherence` | Adherence |
| `POST` | `/api/medicines/doses/action` | Dose Action |
| `GET` | `/api/medicines/frequency-preview` | Frequency Preview |
| `GET` | `/api/medicines/history` | History |
| `GET` | `/api/medicines/today` | Today |
| `DELETE` | `/api/medicines/{med_id}` | Stop Medicine |
| `PUT` | `/api/medicines/{med_id}` | Update Medicine |
| `PATCH` | `/api/medicines/{med_id}/stock` | Update Stock |
| `GET` | `/api/prescriptions` | Prescriptions |

## Notifications

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/notifications` | List Notifications |
| `GET` | `/api/notifications/push/config` | Push Config |
| `DELETE` | `/api/notifications/push/subscribe` | Unsubscribe |
| `POST` | `/api/notifications/push/subscribe` | Subscribe |
| `POST` | `/api/notifications/read-all` | Read All |
| `GET` | `/api/notifications/reminder-settings` | Get Reminder Settings |
| `PUT` | `/api/notifications/reminder-settings` | Put Reminder Settings |
| `POST` | `/api/notifications/test` | Test Notification |
| `POST` | `/api/notifications/{nid}/read` | Mark Read |

## Nutrition

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/nutrition/foods/{food_id}` | Food Detail |
| `GET` | `/api/nutrition/overview` | Overview |
| `GET` | `/api/nutrition/plan` | Get Plan |
| `POST` | `/api/nutrition/plan/regenerate` | Regenerate |
| `PUT` | `/api/nutrition/plan/swap` | Swap |
| `GET` | `/api/nutrition/recommendations` | Recommendations |

## Other

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Healthcheck |

## Profile

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/consents` | Consents |
| `POST` | `/api/consents` | Set Consent |
| `GET` | `/api/profile` | Get Profile |
| `PUT` | `/api/profile` | Update Profile |
| `POST` | `/api/profile/onboarding` | Onboarding |

## Reports

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/reports` | List Reports |
| `GET` | `/api/reports/parameters/{canonical}/history` | History |
| `GET` | `/api/reports/trends` | Trends |
| `DELETE` | `/api/reports/{report_id}` | Delete Report |
| `GET` | `/api/reports/{report_id}` | Get Report |

## Assistant event stream

`POST /api/assistant/chat` returns `text/event-stream`; each `data:` line is an AG-UI event:
`RUN_STARTED`, `STEP_STARTED/FINISHED`, `TOOL_CALL_START/ARGS/END/RESULT`, `TEXT_MESSAGE_START/CONTENT/END`, `CUSTOM` (`guardrail`, `ui_card`, `citations`, `proposals`), `RUN_FINISHED` / `RUN_ERROR`.
