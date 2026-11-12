"""Retrieval for document-grounded answers.

Hybrid retrieval over the patient's own chunks:
  * BM25 lexical scoring (always available, works offline, handles exact lab names well)
  * dense cosine similarity when an embedding provider is configured
fused with Reciprocal Rank Fusion. Verified structured "fact" chunks (written at confirmation time)
are preferred over raw OCR text, and chunks flagged for possible prompt injection are labelled so
the agent treats them with extra suspicion.

The "vector database" is a table of embeddings filtered by user_id. That is sufficient for a single
patient's corpus (hundreds of chunks); swap in pgvector/Qdrant behind `search()` at scale.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import DocumentChunk
from app.services.llm import get_llm

log = logging.getLogger(__name__)

STOP = set("the a an of to and or in on for is are was were be my me i what which when how do does did with at by from this that it your you".split())
EXPANSIONS = {
    "sugar": ["glucose", "hba1c", "fasting", "diabetes"], "शुगर": ["glucose", "hba1c", "sugar"], "diabetes": ["glucose", "hba1c", "metformin"],
    "cholesterol": ["ldl", "hdl", "triglycerides", "lipid"], "कोलेस्ट्रॉल": ["cholesterol", "ldl", "hdl", "lipid"],
    "kidney": ["creatinine", "urea", "egfr"], "किडनी": ["creatinine", "urea", "kidney"], "thyroid": ["tsh", "levothyroxine"],
    "bp": ["blood", "pressure", "telmisartan", "amlodipine"], "diet": ["salt", "sugar", "avoid", "eat", "diet"], "खाना": ["diet", "food", "eat"],
    "medicine": ["tablet", "tab", "mg", "dose"], "दवा": ["medicine", "tablet", "tab"], "doctor": ["dr", "doctor", "advice"],
    "blood": ["haemoglobin", "hemoglobin", "cbc"],
}


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[\wऀ-ॿ]+", (text or "").lower())
    return [t for t in toks if t not in STOP and len(t) > 1]


def expand(tokens: list[str]) -> list[str]:
    out = list(tokens)
    for t in tokens:
        out.extend(EXPANSIONS.get(t, []))
    return out


def chunk_text(text: str, size: int = 700, overlap: int = 120) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    if len(text) <= size:
        return [text] if text else []
    chunks, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        cut = text.rfind("\n", start + size // 2, end)
        end = cut if cut > 0 and end < len(text) else end
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def _embed(texts: list[str]) -> list[list[float]] | None:
    llm = get_llm()
    if not llm or not texts:
        return None
    try:
        return llm.embed(texts)
    except Exception as exc:  # noqa: BLE001
        log.warning("embedding failed (%s) — continuing with lexical retrieval only", type(exc).__name__)
        return None


def index_chunks(db: Session, user_id: str, *, document_id: str | None, source_type: str, label: str, texts: list[str],
                 verified: bool, injection_flagged: bool = False, replace: bool = True) -> int:
    if replace and document_id:
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id, DocumentChunk.source_type == source_type))
    embs = _embed(texts) or [None] * len(texts)
    for i, (t, e) in enumerate(zip(texts, embs)):
        db.add(DocumentChunk(user_id=user_id, document_id=document_id, source_type=source_type, source_label=label[:255], chunk_index=i,
                             text=t, embedding=e, verified=verified, injection_flagged=injection_flagged))
    db.flush()
    return len(texts)


def index_document_text(db: Session, user_id: str, document_id: str, label: str, text: str, injection_flagged: bool) -> int:
    return index_chunks(db, user_id, document_id=document_id, source_type="document", label=label, texts=chunk_text(text),
                        verified=False, injection_flagged=injection_flagged)


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def search(db: Session, user_id: str, query: str, k: int = 5, source_types: list[str] | None = None) -> list[dict]:
    q = select(DocumentChunk).where(DocumentChunk.user_id == user_id)
    if source_types:
        q = q.where(DocumentChunk.source_type.in_(source_types))
    chunks = db.scalars(q).all()
    if not chunks:
        return []
    docs = [tokenize(c.text or "") + tokenize(c.source_label) for c in chunks]
    avgdl = sum(len(d) for d in docs) / len(docs) or 1
    df = Counter(t for d in docs for t in set(d))
    qtoks = expand(tokenize(query))
    k1, b = 1.4, 0.75
    bm25 = []
    for i, d in enumerate(docs):
        tf = Counter(d)
        s = 0.0
        for t in qtoks:
            if t in tf:
                idf = math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / avgdl))
        if chunks[i].verified:
            s *= 1.25  # prefer patient-verified facts over raw OCR
        bm25.append((s, i))
    ranked_lex = [i for s, i in sorted(bm25, reverse=True) if s > 0]
    ranked_dense: list[int] = []
    if any(c.embedding for c in chunks):
        qe = _embed([query])
        if qe:
            dense = [(_cos(qe[0], c.embedding), i) for i, c in enumerate(chunks) if c.embedding]
            ranked_dense = [i for s, i in sorted(dense, reverse=True)[: k * 3]]
    # Reciprocal Rank Fusion
    fused: dict[int, float] = {}
    for ranking in (ranked_lex, ranked_dense):
        for r, i in enumerate(ranking):
            fused[i] = fused.get(i, 0) + 1 / (60 + r)
    order = sorted(fused, key=fused.get, reverse=True)[:k]
    return [{"chunk_id": chunks[i].id, "document_id": chunks[i].document_id, "source": chunks[i].source_label, "source_type": chunks[i].source_type,
             "text": chunks[i].text, "verified": chunks[i].verified, "injection_flagged": chunks[i].injection_flagged, "score": round(fused[i], 4)}
            for i in order]
