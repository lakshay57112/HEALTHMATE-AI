# Security & medical safety

## Data protection
- **Authentication:** bcrypt (12 rounds) password hashes; JWT session in an HTTP-only, SameSite=Lax cookie (`COOKIE_SECURE=true` behind HTTPS); optional Bearer tokens for API/MCP clients.
- **Authorization:** role checks (`require_patient`, `require_caregiver`) and per-resource ownership checks on every route; caregivers reach data only through `/caregiver/*` with permission filtering.
- **Encryption at rest:** uploaded files are Fernet-encrypted before touching disk; OCR text, extraction payloads, notes, chat content, memories and proposals use encrypted columns. Set `ENCRYPTION_KEY` in production (and back it up).
- **Upload validation:** magic-byte sniffing (PDF/JPEG/PNG only), size limit, path-safe storage keys, no client-supplied paths.
- **Headers:** `X-Content-Type-Options`, `X-Frame-Options: SAMEORIGIN`, `frame-ancestors 'self'`, `Referrer-Policy`, `Cache-Control: no-store` on API responses.
- **Audit log:** logins, uploads, verifications, views by caregivers, permission changes, exports and deletions — identifiers and action names only, never medical content.
- **Privacy-conscious logging:** a log filter drops tokens/passwords; traces store redacted shapes, not text.
- **User rights:** full JSON export (`/account/export`) and hard deletion (`/account/delete`, files included).

## Consent
- `ConsentRecord` is an append-only ledger. AI processing requires consent before any upload or chat.
- Caregiver sharing requires: active connection **and** the specific permission flag **and** the latest `caregiver_share` consent for that connection = granted. Revoking sets consent to false immediately.

## Medical safety controls (in code, not just prompts)
| Rule | Enforcement |
|---|---|
| No diagnosis | Input classifier + output rewrite (`agent/guardrails.py`); report explanations use non-diagnostic templates |
| No prescribing / dose changes | Input guardrail + output removal of dose-change sentences; schedules never modify `dosage`; doses can't be marked taken >3 h early |
| No invented values or ranges | Grounding validator flags values not in the source; ranges not in the source are deleted; status is computed only from printed ranges |
| No guessing unclear prescriptions | Unparseable frequency → no schedule until the patient chooses slots or unticks; unusual strengths and missing doses flagged with "confirm with your pharmacist" |
| Doctor's instructions first | Nutrition engine treats doctor instructions as hard constraints at the highest priority |
| No sharing without consent | `consent.connection_allows` on every caregiver read and every escalation |
| Meal-delay rule bounded | After-food reminders may follow a delayed meal by ≤ 120 min; beyond that the patient is told to check with their doctor |

## Prompt injection & the lethal trifecta
Documents are untrusted. They are scanned at ingestion (flag shown to the patient), wrapped as data in prompts, and once untrusted text enters an agent run, write tools are removed and blocked. The agent has no tool that can send data outside the app, so even a successful injection has no exfiltration path.

## Reporting
Please report vulnerabilities privately to the maintainer rather than opening a public issue.
