"""Regenerate docs/API.md from the live OpenAPI schema:  python scripts/export_api_docs.py"""
import os
import sys
from pathlib import Path

os.environ.setdefault("REMINDER_ENGINE_ENABLED", "false")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app  # noqa: E402

spec = app.openapi()
lines = ["# HealthMate AI — REST API", "", "Base URL: `/api` (proxied by the Next.js app). Interactive docs: `/api/docs` (Swagger) and `/api/redoc`.", "",
         "Auth: HTTP-only session cookie `hm_session` set by `/auth/login`, `/auth/register` or `/auth/demo`; or `Authorization: Bearer <token>` (from `POST /auth/token`).",
         "Errors: `{\"detail\": \"human readable message\", \"errors\"?: [{field, message}]}` with 4xx/5xx status.", ""]
by_tag: dict[str, list] = {}
for path, ops in spec["paths"].items():
    for method, op in ops.items():
        by_tag.setdefault((op.get("tags") or ["other"])[0], []).append((path, method.upper(), op))
for tag in sorted(by_tag):
    lines += [f"## {tag.title()}", "", "| Method | Path | Description |", "|---|---|---|"]
    for path, method, op in sorted(by_tag[tag]):
        desc = (op.get("description") or op.get("summary") or "").strip().split("\n")[0]
        lines.append(f"| `{method}` | `{path}` | {desc} |")
    lines.append("")
lines += ["## Assistant event stream", "", "`POST /api/assistant/chat` returns `text/event-stream`; each `data:` line is an AG-UI event:",
          "`RUN_STARTED`, `STEP_STARTED/FINISHED`, `TOOL_CALL_START/ARGS/END/RESULT`, `TEXT_MESSAGE_START/CONTENT/END`, `CUSTOM` (`guardrail`, `ui_card`, `citations`, `proposals`), `RUN_FINISHED` / `RUN_ERROR`.", ""]
out = Path(__file__).resolve().parents[2] / "docs" / "API.md"
out.write_text("\n".join(lines))
print(f"wrote {out} ({sum(len(v) for v in by_tag.values())} endpoints)")
