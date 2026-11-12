from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serializers import appointment_out, iso, measurement_out
from app.core.config import get_settings
from app.core.security import require_patient
from app.db.session import get_db
from app.models import AgentMemory, AgentProposal, AgentTrace, Appointment, ChatMessage, HealthMeasurement, User
from app.services import timeutil
from app.services.agent.harness import run_agent
from app.services.agent.tools import TOOLS
from app.services.audit import audit
from app.services.consent import has_consent
from app.services.llm import get_llm

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


@router.post("/chat")
def chat(body: ChatIn, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    """Streams AG-UI events as Server-Sent Events."""
    if not has_consent(db, user.id, "ai_processing"):
        raise HTTPException(403, "Please allow AI processing in Settings → Privacy to use the assistant.")
    session_id = body.session_id or str(uuid.uuid4())
    audit(db, "assistant.chat", actor_id=user.id, resource_type="chat_session", resource_id=session_id, request=request, commit=True)

    def stream():
        for ev in run_agent(user.id, session_id, body.message.strip()):
            yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-Session-Id": session_id})


@router.get("/status")
def status():
    s = get_settings()
    llm = get_llm()
    return {"mode": "llm" if llm else "demo", "provider": llm.name if llm else None, "model": llm.model if llm else "rule-based-demo",
            "tools": [{"name": t.name, "description": t.description, "writes": t.writes, "reads_untrusted": t.reads_untrusted, "external": t.external} for t in TOOLS.values()],
            "max_steps": s.agent_max_steps}


@router.get("/sessions")
def sessions(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rows = db.execute(select(ChatMessage.session_id, func.min(ChatMessage.created_at), func.max(ChatMessage.created_at), func.count())
                      .where(ChatMessage.user_id == user.id).group_by(ChatMessage.session_id).order_by(func.max(ChatMessage.created_at).desc()).limit(30)).all()
    out = []
    for sid, start, last, n in rows:
        first = db.scalar(select(ChatMessage).where(ChatMessage.session_id == sid, ChatMessage.role == "user").order_by(ChatMessage.created_at).limit(1))
        out.append({"id": sid, "title": (first.content[:60] if first else "Conversation"), "started_at": iso(start), "last_at": iso(last), "messages": n})
    return {"items": out}


@router.get("/sessions/{sid}/messages")
def session_messages(sid: str, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rows = db.scalars(select(ChatMessage).where(ChatMessage.user_id == user.id, ChatMessage.session_id == sid).order_by(ChatMessage.created_at)).all()
    props = {p.id: p.status for p in db.scalars(select(AgentProposal).where(AgentProposal.user_id == user.id))}
    items = []
    for r in rows:
        meta = dict(r.meta or {})
        if meta.get("proposals"):
            meta["proposals"] = [{**p, "status": props.get(p["id"], "expired")} for p in meta["proposals"]]
        items.append({"id": r.id, "role": r.role, "content": r.content, "meta": meta, "created_at": iso(r.created_at)})
    return {"items": items}


@router.delete("/sessions/{sid}")
def delete_session(sid: str, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    db.query(ChatMessage).filter(ChatMessage.user_id == user.id, ChatMessage.session_id == sid).delete()
    db.commit()
    return {"ok": True}


@router.post("/proposals/{pid}/{decision}")
def decide(pid: str, decision: str, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    """Human-in-the-loop: the only path by which an agent proposal changes data."""
    if decision not in ("approve", "reject"):
        raise HTTPException(404, "Unknown decision")
    p = db.get(AgentProposal, pid)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Proposal not found")
    if p.status != "pending":
        raise HTTPException(409, f"Already {p.status}")
    if (timeutil.now_utc() - timeutil.ensure_aware(p.created_at)).total_seconds() > 86400:
        p.status = "expired"
        db.commit()
        raise HTTPException(410, "This suggestion has expired")
    result = None
    if decision == "approve":
        data = p.payload
        tz = user.profile.timezone if user.profile else None
        if p.action == "create_appointment":
            from datetime import date as _date

            a = Appointment(user_id=user.id, doctor_name=data["doctor_name"], clinic=data.get("clinic"), specialization=data.get("specialization"),
                            scheduled_at=timeutil.local_dt(_date.fromisoformat(data["date"]), data.get("time") or "10:00", tz), notes=data.get("notes"), source="assistant")
            db.add(a)
            db.flush()
            result = {"appointment": appointment_out(a)}
        elif p.action == "log_measurement":
            units = {"blood_pressure": "mmHg", "glucose": "mg/dL", "heart_rate": "bpm", "weight": "kg"}
            m = HealthMeasurement(user_id=user.id, kind=data["kind"], value=data["value"], value2=data.get("value2"), unit=units[data["kind"]],
                                  context=data.get("context"), measured_at=timeutil.now_utc(), source="assistant")
            db.add(m)
            db.flush()
            result = {"measurement": measurement_out(m)}
    p.status = "approved" if decision == "approve" else "rejected"
    p.decided_at = timeutil.now_utc()
    audit(db, f"assistant.proposal_{p.status}", actor_id=user.id, resource_type="agent_proposal", resource_id=p.id, meta={"action": p.action}, request=request)
    db.commit()
    return {"status": p.status, "result": result}


@router.get("/memory")
def memory(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rows = db.scalars(select(AgentMemory).where(AgentMemory.user_id == user.id).order_by(AgentMemory.created_at.desc())).all()
    return {"items": [{"id": m.id, "content": m.content, "source": m.source, "created_at": iso(m.created_at)} for m in rows]}


@router.delete("/memory/{mid}")
def forget(mid: str, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    m = db.get(AgentMemory, mid)
    if not m or m.user_id != user.id:
        raise HTTPException(404, "Not found")
    db.delete(m)
    db.commit()
    return {"ok": True}


@router.get("/traces")
def traces(kind: str | None = None, limit: int = 30, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    q = select(AgentTrace).where(AgentTrace.user_id == user.id)
    if kind:
        q = q.where(AgentTrace.kind == kind)
    rows = db.scalars(q.order_by(AgentTrace.created_at.desc()).limit(max(1, min(limit, 100)))).all()
    return {"items": [{"id": t.id, "run_id": t.run_id, "kind": t.kind, "model": t.model, "status": t.status, "total_ms": t.total_ms, "tokens_in": t.tokens_in,
                       "tokens_out": t.tokens_out, "cached_tokens": t.cached_tokens, "guardrail_events": t.guardrail_events, "span_count": len(t.spans or []),
                       "created_at": iso(t.created_at)} for t in rows]}


@router.get("/traces/{tid}")
def trace_detail(tid: str, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    t = db.get(AgentTrace, tid)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Not found")
    return {"trace": {"id": t.id, "run_id": t.run_id, "kind": t.kind, "model": t.model, "status": t.status, "total_ms": t.total_ms, "tokens_in": t.tokens_in,
                      "tokens_out": t.tokens_out, "cached_tokens": t.cached_tokens, "guardrail_events": t.guardrail_events, "spans": t.spans, "created_at": iso(t.created_at)}}
