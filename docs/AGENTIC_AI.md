# Agentic AI design

How each agent-engineering concept is implemented in HealthMate, and where to find it.

| Concept | Implementation | Code |
|---|---|---|
| **Multi-agent system** | Document pipeline = specialised agents in a graph: intake → OCR → injection guard → classifier → *type-specific extractor* (lab / prescription / diet / appointment / consultation) → grounding & safety reviewer → human review | `services/extraction/pipeline.py` |
| **Tool calling** | 14 typed tools (Pydantic arg schemas → JSON schema) for medicines, adherence, reports, trends, diet, readings, search, term lookup, proposals, memory | `services/agent/tools.py` |
| **ReAct loop** | Plan → call tools → observe → repeat (max `AGENT_MAX_STEPS`) → answer. Same loop for OpenAI, Gemini and the offline planner | `services/agent/harness.py` |
| **Agent harness** | Owns the loop, budgets, hook execution, event emission, persistence and error handling; models are swappable planners | `harness.py` |
| **Hooks** | `PRE_TOOL_HOOKS` (no-external, taint gate, explicit-memory gate) and `POST_TOOL_HOOKS` (taint marking, citation + proposal collection); before-run and before-response guardrail stages | `harness.py` |
| **Deterministic guardrails** | Input: emergency (112/108/Tele-MANAS), dose change, prescribing, diagnosis. Output: removes dose-change instructions, softens definitive diagnoses, always appends the education-vs-advice disclaimer. Extraction: grounding, plausibility, strength ranges, unparseable frequency, patient-name mismatch | `agent/guardrails.py`, `extraction/validator.py` |
| **Human-in-the-loop** | (1) Every extracted document requires patient verification before any module changes. (2) Agent write actions are *proposals* (`AgentProposal`) executed only via `POST /assistant/proposals/{id}/approve` | `extraction/commit.py`, `routes/assistant.py` |
| **Agentic RAG** | The agent decides when to retrieve; prefers structured verified tools, falls back to `search_health_records`. Hybrid BM25 + dense retrieval fused with RRF, query expansion (EN/HI/Hinglish), verified fact-chunks boosted over raw OCR | `services/rag.py` |
| **Context engineering** | Stable system prefix → fixed-order tool schemas → small dynamic snapshot (date, language, memories) → budgeted conversation window with compression of older turns → truncated tool results with explicit trust labels | `agent/context.py` |
| **Prompt injection defence** | Uploads scanned at ingestion (flag shown in UI); chunks carry `injection_flagged`; untrusted tool output wrapped in `<tool_result trust='untrusted_document_data'>`; **taint tracking**: once untrusted text is in context, write tools are removed from the tool list *and* blocked by a pre-tool hook | `medical_knowledge.scan_injection`, `harness.hook_taint_gate` |
| **Lethal trifecta** | The agent has private data + untrusted content but **no exfiltration channel**: no tool has `external=True`; caregiver alerts are sent only by the deterministic reminder engine under consent | `tools.py` docstring, `reminder_engine.py` |
| **Agent memory** | Short-term: per-session window. Long-term: `AgentMemory` rows written only when the user explicitly asks ("remember…") — enforced by a hook; viewable/deletable in Settings | `context.py`, `tools.t_remember` |
| **Observability** | Every assistant and pipeline run → `AgentTrace` with redacted spans (timings, tool names, token & cached-token counts, guardrail decisions). UI: Settings → AI activity | `services/observability.py` |
| **Prompt caching** | Prefix-stable prompt layout for provider caching (cached tokens recorded); deterministic extraction calls memoised in `llm_cache` by hash(prompt version + model + input) | `services/llm.py` |
| **Structured output validation** | JSON mode → Pydantic validation → one repair retry with the validation errors → fall back to rule-based extractor | `extraction/llm_extractor.py` |
| **Evals / eval harness** | Offline scorecard: extraction accuracy, hallucination flagging, guardrail behaviour, tool selection, injection inertness; thresholds gate CI. Runs against live models when a key is set | `backend/evals/` |
| **AG-UI / generative UI** | Assistant streams AG-UI events over SSE; the chat renders tool-call chips, guardrail notices, and UI cards (medicine list, lab summary, trend chart, appointment, emergency, approval card) | `harness.py`, `frontend/src/app/app/assistant/page.tsx` |
| **MCP** | `mcp_server.py` exposes read-only tools (today's medicines, adherence, appointments, latest report, diet rules) with `readOnlyHint`; Settings → Developer generates a token + Claude Desktop config | `backend/mcp_server.py` |
| **AGENTS.md** | Repository instructions for coding agents | `/AGENTS.md` |
| **Computer-use agents** | Deliberately **not used**: everything is reachable through typed APIs, and screen-driving agents on health data would widen the attack surface without benefit | — |
