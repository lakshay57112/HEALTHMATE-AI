# Testing

## 1. Backend tests (pytest)
```bash
cd backend && . .venv/bin/activate
createdb -O healthmate healthmate_test     # once
pytest -q
```
- `tests/test_units.py` — frequency parsing, meal-relative times, range-only status, canonical names, grounding (invented values/ranges), unclear frequency, unusual strength, patient mismatch, injection scan, input/output guardrails.
- `tests/test_api.py` — auth & validation, consent gate, prescription journey (nothing active before verification; unclear weekly medicine must be handled), lab journey (bilingual summary), injection flag, caregiver permissions & revocation, assistant tools/guardrails/emergency/HITL, taint gating, export & delete.

## 2. Evals
```bash
python -m evals.run_evals     # writes evals/results/latest.{json,md}; exit code ≠ 0 if below threshold
```
Suites: extraction (field accuracy on 3 sample documents incl. an OCR photo), hallucination (6 synthetic model outputs that must be flagged), guardrails (13 cases), agent (12 tool-selection cases + injection inertness). With an API key configured, run the same suites against the live model as a regression gate.

## 3. Frontend
```bash
cd frontend && npm run typecheck && npm run build
```

## 4. Browser journeys (Playwright)
```bash
pip install playwright && playwright install chromium   # or set CHROME_PATH
# with backend on :8000 and frontend on :3000
python e2e/journeys.py
```
Covers: landing → register → onboarding → prescription upload/verify/save → lab upload/verify/analysis (EN + HI) → injection flag → dashboards (desktop + mobile) → medicines, nutrition, planner, food detail → assistant (tools, dose-change guardrail, approval) → appointments, history, family, notifications, reminder settings, AI activity → caregiver dashboard. Screenshots are saved to `e2e/screenshots/`.

## Manual checks worth doing on a real phone
- Voice reminder playback in Hindi (depends on installed device voices).
- Camera upload of a handwritten prescription.
- Web Push with VAPID keys configured, app closed.
- Large-text mode and screen reader labels.
