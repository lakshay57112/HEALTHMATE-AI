"""Agent harness — a ReAct loop with hooks, deterministic guardrails, taint-aware tool gating,
observability, and an AG-UI-style event stream.

    user msg ─► [before_run hooks: input guardrails] ─► loop {
                    model/planner ─► tool calls ─► [before_tool hooks: policy] ─► tool ─► [after_tool hooks: taint, UI card]
                } ─► [before_response hooks: output guardrails, disclaimer] ─► stream ─► [after_run: persist memory + trace]

Events follow the AG-UI protocol vocabulary (RUN_STARTED, TOOL_CALL_START/ARGS/END/RESULT,
TEXT_MESSAGE_START/CONTENT/END, CUSTOM, RUN_FINISHED/RUN_ERROR) so any AG-UI client can render the run;
our Next.js chat renders tool calls and "generative UI" cards from CUSTOM ui_card events.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import ChatMessage, User
from app.services.agent import guardrails
from app.services.agent.context import SYSTEM_PREFIX, conversation_window, detect_language, patient_snapshot, tool_result_message
from app.services.agent.demo_policy import DemoPlanner
from app.services.agent.tools import TOOLS, ToolContext, run_tool
from app.services.llm import BaseLLM, LLMError, LLMResponse, get_llm
from app.services.observability import Tracer, redact

log = logging.getLogger(__name__)


@dataclass
class RunState:
    ctx: ToolContext
    tracer: Tracer
    lang: str
    tool_log: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    proposals: list[dict] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ hooks
PreToolHook = Callable[[RunState, str, dict], str | None]  # returns a block reason or None
PostToolHook = Callable[[RunState, str, dict], None]


def hook_taint_gate(st: RunState, name: str, args: dict) -> str | None:
    """Once untrusted document text is in context, no state-changing tool may run in this turn."""
    tool = TOOLS.get(name)
    if tool and tool.writes and st.ctx.tainted:
        return "Blocked: write actions are disabled after reading untrusted document text (prompt-injection defence)."
    return None


def hook_no_external(st: RunState, name: str, args: dict) -> str | None:
    tool = TOOLS.get(name)
    if tool and tool.external:
        return "Blocked: the assistant cannot send data outside the app."
    return None


def hook_explicit_memory(st: RunState, name: str, args: dict) -> str | None:
    if name == "remember_preference" and not re.search(r"\b(remember|yaad)\b|याद", st.ctx.last_user_message, re.I):
        return "Blocked: memory can only be saved when the patient explicitly asks."
    return None


def hook_mark_taint(st: RunState, name: str, result: dict) -> None:
    tool = TOOLS.get(name)
    if tool and tool.reads_untrusted and result.get("results"):
        st.ctx.tainted = True
        st.tracer.guardrail("taint", "tainted", f"{name} returned untrusted text; write tools disabled")
        for r in result["results"]:
            st.citations.append({"source": r["source"], "verified": r["verified"], "document_id": r.get("document_id"), "flagged": r.get("possible_injection", False)})
            if r.get("possible_injection"):
                st.tracer.guardrail("injection_in_retrieval", "flagged", r["source"])


def hook_collect_proposals(st: RunState, name: str, result: dict) -> None:
    if result.get("proposal_id"):
        st.proposals.append({"id": result["proposal_id"], "summary": result.get("summary"), "action": name})


PRE_TOOL_HOOKS: list[PreToolHook] = [hook_no_external, hook_taint_gate, hook_explicit_memory]
POST_TOOL_HOOKS: list[PostToolHook] = [hook_mark_taint, hook_collect_proposals]


# ------------------------------------------------------------------ planner adapters
class LLMPlanner:
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.name, self.model = llm.name, llm.model

    def next(self, system: str, messages: list[dict], tools_available: set[str]) -> LLMResponse:
        schemas = [TOOLS[n].schema() for n in TOOLS if n in tools_available]  # fixed order → cache-friendly
        clean = [{k: v for k, v in m.items() if k != "raw"} for m in messages]
        return self.llm.chat(system, clean, tools=schemas, temperature=0.2)


def _ev(type_: str, **data) -> dict:
    return {"type": type_, **data}


def available_tools(ctx: ToolContext) -> set[str]:
    return {n for n, t in TOOLS.items() if not t.external and not (t.writes and ctx.tainted)}


def run_agent(user_id: str, session_id: str, message: str) -> Iterator[dict]:
    settings = get_settings()
    db = SessionLocal()
    run_id = str(uuid.uuid4())
    try:
        user = db.get(User, user_id)
        lang = detect_language(message, user)
        llm = get_llm()
        planner = LLMPlanner(llm) if llm else DemoPlanner()
        tracer = Tracer("assistant", user.id, model=f"{planner.name}:{planner.model}", run_id=run_id)
        ctx = ToolContext(db=db, user=user, run_id=run_id, lang=lang, last_user_message=message)
        st = RunState(ctx=ctx, tracer=tracer, lang=lang)
        yield _ev("RUN_STARTED", runId=run_id, threadId=session_id, mode="llm" if llm else "demo", model=tracer.model, lang=lang)

        # ---- before_run: input guardrails
        with tracer.span("input_guardrails", kind="guardrail") as sp:
            check = guardrails.check_input(message)
            sp.set(**{k: getattr(check, k) for k in ("emergency", "dose_change", "prescribe", "diagnosis")})
        for e in check.events:
            tracer.guardrail(e["guardrail"], e["decision"])
            yield _ev("CUSTOM", name="guardrail", value=e)

        history = conversation_window(db, user.id, session_id)
        db.add(ChatMessage(user_id=user.id, session_id=session_id, role="user", content=message, meta={"run_id": run_id}))
        db.flush()

        final_text = ""
        if check.emergency:
            final_text = guardrails.emergency_reply(lang, check.self_harm)
            yield _ev("CUSTOM", name="ui_card", value={"type": "emergency", "data": {"numbers": [{"label": "Emergency", "number": "112"}, {"label": "Ambulance", "number": "108"}]
                                                                                    + ([{"label": "Tele-MANAS", "number": "14416"}] if check.self_harm else [])}})
        else:
            system = SYSTEM_PREFIX + patient_snapshot(db, user, lang)
            messages: list[dict] = history + [{"role": "user", "content": message}]
            for step in range(settings.agent_max_steps):
                yield _ev("STEP_STARTED", stepName=f"reason_{step + 1}")
                tools_now = available_tools(ctx)
                with tracer.span(f"plan_{step + 1}", kind="llm", tools_offered=len(tools_now)) as sp:
                    if isinstance(planner, DemoPlanner):
                        resp = planner.next(messages, tools_now, lang)
                    else:
                        resp = planner.next(system, messages, tools_now)
                    tracer.add_usage(resp.usage)
                    sp.set(tool_calls=[c.name for c in resp.tool_calls], **{k: v for k, v in (resp.usage or {}).items()})
                yield _ev("STEP_FINISHED", stepName=f"reason_{step + 1}")
                if not resp.tool_calls:
                    final_text = resp.text or ""
                    break
                messages.append({"role": "assistant", "content": resp.text or "", "tool_calls": [{"id": c.id, "name": c.name, "arguments": c.arguments} for c in resp.tool_calls]})
                for call in resp.tool_calls:
                    yield _ev("TOOL_CALL_START", toolCallId=call.id, toolCallName=call.name)
                    yield _ev("TOOL_CALL_ARGS", toolCallId=call.id, delta=json.dumps(call.arguments, ensure_ascii=False))
                    yield _ev("TOOL_CALL_END", toolCallId=call.id)
                    reason = next((r for h in PRE_TOOL_HOOKS if (r := h(st, call.name, call.arguments))), None)
                    with tracer.span(f"tool:{call.name}", kind="tool", args=redact(call.arguments)) as sp:
                        if reason:
                            result = {"error": reason}
                            st.blocked.append(call.name)
                            tracer.guardrail("pre_tool_policy", "blocked", f"{call.name}: {reason}")
                            sp.status = "blocked"
                            yield _ev("CUSTOM", name="guardrail", value={"guardrail": "pre_tool_policy", "decision": "blocked", "tool": call.name, "detail": reason})
                        else:
                            result = run_tool(ctx, call.name, call.arguments)
                            for h in POST_TOOL_HOOKS:
                                h(st, call.name, result)
                        sp.set(result_shape=redact(result) if isinstance(result, dict) else None)
                    tool = TOOLS.get(call.name)
                    untrusted = bool(tool and tool.reads_untrusted)
                    yield _ev("TOOL_CALL_RESULT", toolCallId=call.id, toolCallName=call.name, ok="error" not in result, untrusted=untrusted)
                    if tool and tool.ui_card and "error" not in result:
                        yield _ev("CUSTOM", name="ui_card", value={"type": tool.ui_card, "tool": call.name, "data": result})
                    st.tool_log.append({"tool": call.name, "ok": "error" not in result, "blocked": bool(reason)})
                    messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": tool_result_message(call.name, result, untrusted),
                                     "raw": json.dumps(result, ensure_ascii=False, default=str)})
            else:
                final_text = "मैं अभी उत्तर पूरा नहीं कर सका। कृपया प्रश्न छोटा करके पूछें।" if lang == "hi" else "I couldn't finish that just now. Could you ask in a simpler way?"

            # ---- before_response: output guardrails + policy note + disclaimer
            with tracer.span("output_guardrails", kind="guardrail") as sp:
                final_text, out_events = guardrails.check_output(final_text, lang)
                sp.set(events=len(out_events))
            for e in out_events:
                tracer.guardrail(e["guardrail"], e["decision"])
                yield _ev("CUSTOM", name="guardrail", value=e)
            note = guardrails.policy_note(check, lang)
            if note:
                final_text = f"{note}\n\n{final_text}".strip()
            final_text = f"{final_text}\n\n{guardrails.DISCLAIMER[lang]}"

        msg_id = str(uuid.uuid4())
        yield _ev("TEXT_MESSAGE_START", messageId=msg_id, role="assistant")
        for i in range(0, len(final_text), 48):
            yield _ev("TEXT_MESSAGE_CONTENT", messageId=msg_id, delta=final_text[i : i + 48])
        yield _ev("TEXT_MESSAGE_END", messageId=msg_id)
        if st.citations:
            yield _ev("CUSTOM", name="citations", value=st.citations)
        if st.proposals:
            yield _ev("CUSTOM", name="proposals", value=st.proposals)

        db.add(ChatMessage(user_id=user.id, session_id=session_id, role="assistant", content=final_text,
                           meta={"run_id": run_id, "tools": st.tool_log, "citations": st.citations, "proposals": st.proposals, "mode": "llm" if llm else "demo",
                                 "guardrails": tracer.guardrail_events, "tainted": ctx.tainted}))
        tracer.persist(db)
        db.commit()
        yield _ev("RUN_FINISHED", runId=run_id, threadId=session_id)
    except LLMError as exc:
        db.rollback()
        log.warning("LLM error in agent run: %s", exc)
        yield _ev("RUN_ERROR", message="The AI service is unavailable right now. Please try again in a moment.", code="llm_unavailable")
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("agent run failed")
        yield _ev("RUN_ERROR", message="Something went wrong. Please try again.", code="internal")
    finally:
        db.close()
