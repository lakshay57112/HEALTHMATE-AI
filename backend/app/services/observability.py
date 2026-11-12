"""Lightweight tracing for agent + pipeline runs.

Spans hold timings, token counts, tool names and guardrail decisions. They are *redacted*:
we record shapes and counts, not medical content, so traces are safe to inspect.
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models import AgentTrace


def redact(value: Any, limit: int = 80) -> Any:
    """Keep structure, drop content. Strings become length markers; numbers survive."""
    if isinstance(value, str):
        return f"<str:{len(value)}>" if len(value) > 24 else value
    if isinstance(value, dict):
        return {k: redact(v, limit) for k, v in list(value.items())[:20]}
    if isinstance(value, list):
        return [redact(v, limit) for v in value[:5]] + ([f"…+{len(value) - 5}"] if len(value) > 5 else [])
    return value


@dataclass
class Span:
    name: str
    kind: str
    start: float
    attrs: dict = field(default_factory=dict)
    duration_ms: int = 0
    status: str = "ok"

    def set(self, **attrs: Any) -> None:
        self.attrs.update(attrs)

    def to_dict(self, t0: float) -> dict:
        return {"name": self.name, "kind": self.kind, "offset_ms": int((self.start - t0) * 1000), "duration_ms": self.duration_ms,
                "status": self.status, "attrs": self.attrs}


class Tracer:
    def __init__(self, kind: str, user_id: str, model: str = "unknown", run_id: str | None = None):
        self.kind = kind
        self.user_id = user_id
        self.model = model
        self.run_id = run_id or str(uuid.uuid4())
        self.t0 = time.perf_counter()
        self.spans: list[Span] = []
        self.tokens_in = self.tokens_out = self.cached_tokens = 0
        self.guardrail_events: list[dict] = []
        self.status = "ok"

    @contextmanager
    def span(self, name: str, kind: str = "step", **attrs: Any):
        sp = Span(name=name, kind=kind, start=time.perf_counter(), attrs=dict(attrs))
        self.spans.append(sp)
        try:
            yield sp
        except Exception as exc:
            sp.status = "error"
            sp.attrs["error"] = type(exc).__name__
            raise
        finally:
            sp.duration_ms = int((time.perf_counter() - sp.start) * 1000)

    def add_usage(self, usage: dict | None) -> None:
        if not usage:
            return
        self.tokens_in += int(usage.get("input_tokens", 0) or 0)
        self.tokens_out += int(usage.get("output_tokens", 0) or 0)
        self.cached_tokens += int(usage.get("cached_tokens", 0) or 0)

    def guardrail(self, name: str, decision: str, detail: str = "") -> None:
        self.guardrail_events.append({"guardrail": name, "decision": decision, "detail": detail[:160]})

    def persist(self, db: Session) -> AgentTrace:
        trace = AgentTrace(
            user_id=self.user_id, run_id=self.run_id, kind=self.kind, model=self.model, status=self.status,
            spans=[s.to_dict(self.t0) for s in self.spans], total_ms=int((time.perf_counter() - self.t0) * 1000),
            tokens_in=self.tokens_in, tokens_out=self.tokens_out, cached_tokens=self.cached_tokens, guardrail_events=self.guardrail_events,
        )
        db.add(trace)
        return trace
