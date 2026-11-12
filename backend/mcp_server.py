"""HealthMate MCP server — exposes a patient's own HealthMate data to MCP clients (e.g. Claude Desktop)
as READ-ONLY tools, by calling the HealthMate REST API with the patient's bearer token.

Design choices:
  * read-only (readOnlyHint) — no tool can modify data or contact anyone (no exfiltration channel)
  * scoped to one patient via their own API token (get one from Settings → Developer, or POST /api/auth/token)
  * returns verified, structured data; document search results are labelled untrusted

Run (stdio):
    HEALTHMATE_API_URL=http://localhost:8000/api HEALTHMATE_TOKEN=<token> python mcp_server.py

Claude Desktop config example:
    {"mcpServers": {"healthmate": {"command": "python", "args": ["/path/to/backend/mcp_server.py"],
      "env": {"HEALTHMATE_API_URL": "http://localhost:8000/api", "HEALTHMATE_TOKEN": "<token>"}}}}
"""
from __future__ import annotations

import os

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

API = os.environ.get("HEALTHMATE_API_URL", "http://localhost:8000/api").rstrip("/")
TOKEN = os.environ.get("HEALTHMATE_TOKEN", "")
RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

server = MCPServer(
    name="healthmate",
    title="HealthMate AI",
    instructions="Read-only access to the patient's verified HealthMate records. Never give diagnoses or change medicine doses; refer to the doctor.",
    version="1.0.0",
)


def _get(path: str, **params) -> dict:
    if not TOKEN:
        raise RuntimeError("HEALTHMATE_TOKEN is not set")
    r = httpx.get(f"{API}{path}", params=params, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=20)
    r.raise_for_status()
    return r.json()


@server.tool(description="Today's scheduled medicine doses with time, dose, meal timing and status.", annotations=RO)
def todays_medicines() -> dict:
    d = _get("/medicines/today")
    return {"date": d["date"], "doses": [{k: x[k] for k in ("name", "strength", "dosage", "effective_time", "meal_relation", "status")} for x in d["doses"]]}


@server.tool(description="Medicine adherence over the last N days (default 7).", annotations=RO)
def adherence(days: int = 7) -> dict:
    d = _get("/medicines/adherence", days=days)
    return {"percent": d["percent"], "taken": d["taken"], "expected": d["expected"]}


@server.tool(description="Upcoming doctor appointments.", annotations=RO)
def upcoming_appointments() -> dict:
    d = _get("/appointments", scope="upcoming")
    return {"appointments": [{k: a[k] for k in ("doctor_name", "specialization", "clinic", "scheduled_at")} for a in d["items"][:5]]}


@server.tool(description="The latest verified lab report: each parameter with value, printed range and status.", annotations=RO)
def latest_lab_report() -> dict:
    items = _get("/reports")["items"]
    if not items:
        return {"report": None}
    r = _get(f"/reports/{items[0]['id']}")["report"]
    return {"title": r["title"], "date": r["report_date"], "sample_data": r["is_sample"],
            "parameters": [{k: p[k] for k in ("name", "value_text", "unit", "ref_text", "status")} for p in r["parameters"]]}


@server.tool(description="Doctor's diet instructions and active meal-plan rules.", annotations=RO)
def diet_rules() -> dict:
    d = _get("/nutrition/overview")
    return {"doctor_instructions": d["doctor_instructions"], "rules": [{"rule": x["label"], "why": x["source"]} for x in d["rules"]]}


if __name__ == "__main__":
    server.run()
