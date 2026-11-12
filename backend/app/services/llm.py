"""Provider-agnostic LLM client (OpenAI / Gemini over REST) with tool calling, JSON mode,
embeddings and a response cache.

Prompt caching: callers build prompts as [stable system prefix → tool schemas → patient
context → conversation]. Both OpenAI (automatic prefix caching ≥1024 tokens) and Gemini
(implicit caching) bill repeated prefixes at a discount; cached token counts are read from
the usage block and recorded in traces. Deterministic calls (temperature 0, e.g. document
extraction) are additionally memoised in the `llm_cache` table.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import LLMCache

log = logging.getLogger(__name__)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    model: str = ""
    cached: bool = False


class LLMError(RuntimeError):
    pass


class BaseLLM:
    name = "base"
    model = "none"

    def chat(self, system: str, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = False,
             temperature: float = 0.0) -> LLMResponse:
        raise NotImplementedError

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        return None


class OpenAILLM(BaseLLM):
    name = "openai"

    def __init__(self, api_key: str, model: str, embedding_model: str, base_url: str, timeout: int):
        self.model = model
        self.embedding_model = embedding_model
        self.client = httpx.Client(base_url=base_url, timeout=timeout, headers={"Authorization": f"Bearer {api_key}"})

    def chat(self, system, messages, tools=None, json_mode=False, temperature=0.0):  # noqa: ANN001
        msgs: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for m in messages:
            if m["role"] == "tool":
                msgs.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            elif m["role"] == "assistant" and m.get("tool_calls"):
                msgs.append({"role": "assistant", "content": m.get("content") or None, "tool_calls": [
                    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])}}
                    for tc in m["tool_calls"]]})
            else:
                msgs.append({"role": m["role"], "content": m["content"]})
        body: dict[str, Any] = {"model": self.model, "messages": msgs, "temperature": temperature}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = self.client.post("/chat/completions", json=body)
        if r.status_code >= 400:
            raise LLMError(f"OpenAI error {r.status_code}")
        data = r.json()
        choice = data["choices"][0]["message"]
        calls = [ToolCall(tc["id"], tc["function"]["name"], json.loads(tc["function"]["arguments"] or "{}")) for tc in choice.get("tool_calls") or []]
        u = data.get("usage", {})
        usage = {"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0),
                 "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)}
        return LLMResponse(choice.get("content"), calls, usage, self.model)

    def embed(self, texts):  # noqa: ANN001
        r = self.client.post("/embeddings", json={"model": self.embedding_model, "input": texts})
        if r.status_code >= 400:
            raise LLMError(f"OpenAI embeddings error {r.status_code}")
        return [d["embedding"] for d in r.json()["data"]]


class GeminiLLM(BaseLLM):
    name = "gemini"
    BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str, model: str, embedding_model: str, timeout: int):
        self.model = model
        self.embedding_model = embedding_model
        self.client = httpx.Client(timeout=timeout, headers={"x-goog-api-key": api_key})

    def chat(self, system, messages, tools=None, json_mode=False, temperature=0.0):  # noqa: ANN001
        contents = []
        for m in messages:
            if m["role"] == "tool":
                contents.append({"role": "user", "parts": [{"functionResponse": {"name": m["name"], "response": {"result": m["content"]}}}]})
            elif m["role"] == "assistant" and m.get("tool_calls"):
                contents.append({"role": "model", "parts": [{"functionCall": {"name": tc["name"], "args": tc["arguments"]}} for tc in m["tool_calls"]]})
            else:
                contents.append({"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]})
        body: dict[str, Any] = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                                "generationConfig": {"temperature": temperature}}
        if tools:
            body["tools"] = [{"functionDeclarations": tools}]
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        r = self.client.post(f"{self.BASE}/models/{self.model}:generateContent", json=body)
        if r.status_code >= 400:
            raise LLMError(f"Gemini error {r.status_code}")
        data = r.json()
        parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts) or None
        calls = [ToolCall(f"call_{i}", p["functionCall"]["name"], p["functionCall"].get("args", {})) for i, p in enumerate(parts) if "functionCall" in p]
        u = data.get("usageMetadata", {})
        usage = {"input_tokens": u.get("promptTokenCount", 0), "output_tokens": u.get("candidatesTokenCount", 0),
                 "cached_tokens": u.get("cachedContentTokenCount", 0)}
        return LLMResponse(text, calls, usage, self.model)

    def embed(self, texts):  # noqa: ANN001
        out = []
        for t in texts:
            r = self.client.post(f"{self.BASE}/models/{self.embedding_model}:embedContent",
                                 json={"content": {"parts": [{"text": t}]}})
            if r.status_code >= 400:
                raise LLMError(f"Gemini embeddings error {r.status_code}")
            out.append(r.json()["embedding"]["values"])
        return out


def get_llm() -> BaseLLM | None:
    """Return a configured provider, or None when running in demo mode."""
    s = get_settings()
    if s.llm_provider == "openai" and s.openai_api_key:
        return OpenAILLM(s.openai_api_key, s.openai_model, s.openai_embedding_model, s.openai_base_url, s.llm_timeout_seconds)
    if s.llm_provider == "gemini" and s.gemini_api_key:
        return GeminiLLM(s.gemini_api_key, s.gemini_model, s.gemini_embedding_model, s.llm_timeout_seconds)
    return None


def cache_key(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def cached_json_call(db: Session, llm: BaseLLM, prompt_version: str, system: str, user: str) -> tuple[dict, dict, bool]:
    """Deterministic JSON call with DB memoisation. Returns (parsed_json, usage, cache_hit)."""
    key = cache_key(prompt_version, llm.name, llm.model, system, user)
    hit = db.get(LLMCache, key)
    if hit:
        hit.hits += 1
        return hit.response, {}, True
    resp = llm.chat(system, [{"role": "user", "content": user}], json_mode=True, temperature=0)
    try:
        parsed = json.loads(resp.text or "{}")
    except json.JSONDecodeError as exc:
        raise LLMError("Model did not return valid JSON") from exc
    db.add(LLMCache(key=key, model=f"{llm.name}:{llm.model}", response=parsed))
    return parsed, resp.usage, False
