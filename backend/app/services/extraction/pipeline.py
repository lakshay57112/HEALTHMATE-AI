"""Document intelligence pipeline — a small multi-agent graph.

    intake → ocr → injection_guard → classifier → specialist extractor → grounding/safety review → human review

Each node is a focused "agent" with one job. Routing to the specialist extractor is conditional on
the detected type. Progress is persisted after every node so the UI can show live status, and the
whole run is traced (see services.observability).

The pipeline NEVER writes to medicines, reports or appointments. It stops at `needs_review`; only the
patient's confirmation (services.extraction.commit) changes connected modules — human-in-the-loop.
"""
from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import MedicalDocument, User
from app.services import ocr as ocr_service
from app.services.extraction import rules
from app.services.extraction.llm_extractor import llm_extract
from app.services.extraction.validator import validate
from app.services.llm import LLMError, get_llm
from app.services.medical_knowledge import scan_injection, strip_injection_lines
from app.services.observability import Tracer
from app.services.storage import load_file

log = logging.getLogger(__name__)

STEP_LABELS = {
    "intake": "Checking your file",
    "ocr": "Reading the text",
    "injection_guard": "Security check",
    "classifier": "Detecting document type",
    "extractor": "Extracting information",
    "review": "Double-checking every value",
    "ready": "Ready for your review",
}

State = dict[str, Any]
Node = Callable[[Session, State, Tracer], State]


def node_intake(db: Session, st: State, tr: Tracer) -> State:
    doc: MedicalDocument = st["doc"]
    st["data"] = load_file(doc.storage_key)
    return {"detail": f"{doc.mime_type}, {round(doc.size_bytes / 1024)} KB"}


def node_ocr(db: Session, st: State, tr: Tracer) -> State:
    res = ocr_service.extract_text(st["data"], st["doc"].mime_type)
    st.update(text=res.text, ocr_method=res.method, ocr_conf=res.mean_confidence, warnings=res.warnings or [])
    if res.method == "unavailable" or len(res.text.strip()) < 20:
        st["unreadable"] = True
        return {"detail": "Could not read text", "status": "warning"}
    return {"detail": f"{res.method}, {len(res.text)} characters" + (f", OCR confidence {round(res.mean_confidence * 100)}%" if res.mean_confidence else "")}


def node_injection_guard(db: Session, st: State, tr: Tracer) -> State:
    hits = scan_injection(st.get("text", ""))
    st["injection_hits"] = hits
    # Extraction and grounding only ever see the cleaned text, so injected lines cannot become data or titles.
    st["clean_text"] = strip_injection_lines(st.get("text", "")) if hits else st.get("text", "")
    tr.guardrail("prompt_injection_scan", "flagged" if hits else "pass", ", ".join(hits))
    return {"detail": "Suspicious instructions found and neutralised" if hits else "No hidden instructions found", "status": "warning" if hits else "ok"}


def node_classifier(db: Session, st: State, tr: Tracer) -> State:
    detected, conf, scores = rules.classify(st.get("clean_text", st.get("text", "")))
    declared = st["doc"].declared_type
    st["type_scores"] = scores
    if declared and declared != "auto":
        # The patient's choice wins; we only flag strong disagreement.
        st["detected_type"], st["type_confidence"] = declared, max(conf, 0.8)
        if detected not in (declared, "other") and scores.get(detected, 0) >= scores.get(declared, 0) + 3:
            st.setdefault("extra_flags", []).append({"code": "type_mismatch", "severity": "warning", "path": None,
                                                     "message": f"This looks like a {detected.replace('_', ' ')}, but it was uploaded as a {declared.replace('_', ' ')}."})
    else:
        st["detected_type"], st["type_confidence"] = detected, conf
    return {"detail": f"{st['detected_type'].replace('_', ' ')} ({round(st['type_confidence'] * 100)}%)"}


def node_extractor(db: Session, st: State, tr: Tracer) -> State:
    doc_type = st["detected_type"]
    if doc_type not in rules.EXTRACTORS:
        st["extraction"], st["extractor"], st["base_conf"] = {}, "none", 0.0
        return {"detail": "Stored for your records (no structured data for this type)", "status": "warning"}
    llm = get_llm()
    if llm is not None:
        try:
            with tr.span("llm_extract", kind="llm", doc_type=doc_type, model=llm.model) as sp:
                model, usage, hit = llm_extract(db, llm, doc_type, st.get("clean_text", st["text"]))
                tr.add_usage(usage)
                sp.set(cache_hit=hit, **{k: v for k, v in usage.items()})
            st["extraction"], st["extractor"], st["base_conf"] = model.model_dump(), f"{llm.name}:{llm.model}", 0.88
            return {"detail": f"AI specialist ({llm.name}){' · cached' if hit else ''}"}
        except (LLMError, Exception) as exc:  # noqa: BLE001 — fall back to deterministic rules
            log.warning("LLM extraction failed, falling back to rules: %s", type(exc).__name__)
            st.setdefault("warnings", []).append("AI extraction was unavailable, so the rule-based reader was used.")
    model, meta = rules.EXTRACTORS[doc_type](st.get("clean_text", st["text"]))
    st["extraction"], st["extractor"] = model.model_dump(), "rules-v1"
    st["base_conf"] = 0.9 if meta.get("matched_lines", 1) else 0.5
    return {"detail": f"Rule-based reader · {meta.get('matched_lines', 0)} items" if "matched_lines" in meta else "Rule-based reader"}


def node_review(db: Session, st: State, tr: Tracer) -> State:
    user: User = st["user"]
    text = st.get("clean_text", st.get("text", ""))
    review = validate(st["detected_type"], st.get("extraction") or {}, text, base_confidence=st.get("base_conf", 0.0),
                      ocr_confidence=st.get("ocr_conf"), patient_name=user.full_name)
    review["flags"] = st.get("extra_flags", []) + review["flags"]
    from sqlalchemy import select as _select

    from app.models import PrescriptionMedicine

    active = db.scalars(_select(PrescriptionMedicine).where(PrescriptionMedicine.user_id == user.id, PrescriptionMedicine.is_active.is_(True))).all()
    if st.get("ocr_method") in ("pdf_ocr", "image_ocr"):
        review["flags"].append({"code": "scanned_document", "severity": "warning", "path": None,
                                "message": "This was read from a scan or photo, where numbers are easy to misread (1.7 can become 7). "
                                           "Compare every value with the original before saving."})
    for name in stopped_medicines(text, active):
        review["flags"].append({"code": "stop_instruction", "severity": "high", "path": None,
                                "message": f"This document says to stop {name}, which is still in your medicines. HealthMate never changes your "
                                           "medicines on its own — confirm with your doctor, then pause it on the Medicines page."})
    if st["detected_type"] in ("consultation_note", "diet_advice", "other") and st["doc"].declared_type in (None, "auto"):
        listed, _ = rules.extract_prescription(text)
        if len(listed.medicines) >= 2:
            review["flags"].append({"code": "contains_medicines", "severity": "info", "path": None,
                                    "message": f"This document also lists {len(listed.medicines)} medicines. To add them to your reminders, upload it "
                                               "again and choose 'Prescription' as the document type."})
    if st["detected_type"] == "prescription":
        keyset = {(m.generic_name or m.name).lower().split("+")[0].strip(): m.name for m in active}
        dups = []
        for i, m in enumerate((st.get("extraction") or {}).get("medicines", [])):
            k = (m.get("generic_name") or m.get("name") or "").lower().split("+")[0].strip()
            if k and k in keyset:
                dups.append({"index": i, "existing": keyset[k]})
                review["items"][i]["flags"].append({"code": "already_taking", "severity": "info", "path": f"medicines.{i}",
                                                    "message": f"You already have {keyset[k]} in your medicines. If this is a renewed prescription, replace the old entry."})
        review["duplicates"] = dups
    if st.get("injection_hits"):
        review["flags"].insert(0, {"code": "possible_injection", "severity": "high", "path": None,
                                   "message": "This document contains text that looks like instructions to an AI. It was treated as plain data. Please make sure the document is genuine."})
    for w in st.get("warnings", []):
        review["flags"].append({"code": "reader_warning", "severity": "info", "path": None, "message": w})
    st["review"] = review
    n_high = sum(1 for f in review["flags"] if f["severity"] == "high") + sum(1 for i in review["items"] for f in i["flags"] if f["severity"] == "high")
    tr.guardrail("grounding_and_safety", "flagged" if n_high else "pass", f"{n_high} high-severity flags")
    return {"detail": f"Confidence {round(review['overall_confidence'] * 100)}% · {n_high} item(s) need attention"}


STOP_LINE = re.compile(r"\b(stop|stopped|discontinue|discontinued|band karein|band kar)\b", re.I)


def stopped_medicines(text: str, active: list) -> list[str]:
    """Active medicines named on a line that says stop/discontinue (e.g. a discharge summary). Deterministic."""
    lines = [ln for ln in text.splitlines() if STOP_LINE.search(ln) and not re.search(r"\b(do not|don'?t|never|not to)\s+stop\b", ln, re.I)]
    out: list[str] = []
    for med in active:
        names = {n for n in (med.name, med.brand_name) if n and len(n) >= 4}
        if med.generic_name:
            names |= {g.strip() for g in med.generic_name.split("+") if len(g.strip()) >= 5}
        if any(re.search(rf"(?<![A-Za-z]){re.escape(n)}(?![A-Za-z])", ln, re.I) for n in names for ln in lines) and med.name not in out:
            out.append(med.name)
    return out


GRAPH: list[tuple[str, Node]] = [
    ("intake", node_intake),
    ("ocr", node_ocr),
    ("injection_guard", node_injection_guard),
    ("classifier", node_classifier),
    ("extractor", node_extractor),
    ("review", node_review),
]


def _record(db: Session, doc: MedicalDocument, name: str, status: str, ms: int, detail: str) -> None:
    steps = [s for s in (doc.pipeline_steps or []) if s["step"] != name]
    steps.append({"step": name, "label": STEP_LABELS.get(name, name), "status": status, "ms": ms, "detail": detail})
    doc.pipeline_steps = steps
    db.commit()


def process_document(document_id: str) -> None:
    db = SessionLocal()
    try:
        doc = db.get(MedicalDocument, document_id)
        if not doc:
            return
        user = db.get(User, doc.user_id)
        llm = get_llm()
        tr = Tracer("extraction", user.id, model=f"{llm.name}:{llm.model}" if llm else "rules-v1")
        st: State = {"doc": doc, "user": user}
        doc.status, doc.pipeline_steps, doc.error = "processing", [], None
        db.commit()
        for name, node in GRAPH:
            t0 = time.perf_counter()
            _record(db, doc, name, "running", 0, "")
            with tr.span(name, kind="agent") as sp:
                out = node(db, st, tr) or {}
                sp.set(detail=out.get("detail", ""))
            _record(db, doc, name, out.get("status", "ok"), int((time.perf_counter() - t0) * 1000), out.get("detail", ""))
            if name == "ocr" and st.get("unreadable"):
                break
        if st.get("unreadable"):
            st["detected_type"] = doc.declared_type if doc.declared_type not in (None, "auto") else "other"
            st["extraction"], st["extractor"] = {}, "none"
            st["review"] = {"items": [], "field_confidence": {}, "overall_confidence": 0.0, "needs_attention": [],
                            "flags": [{"code": "unreadable", "severity": "high", "path": None,
                                       "message": "We could not read this document clearly. You can enter the details yourself, or ask your pharmacist/doctor to help."}]
                            + [{"code": "reader_warning", "severity": "info", "path": None, "message": w} for w in st.get("warnings", [])]}
        doc.ocr_text = st.get("text")
        doc.ocr_method = st.get("ocr_method")
        doc.detected_type = st.get("detected_type")
        doc.extractor = st.get("extractor")
        doc.extraction = {"type": doc.detected_type, "data": st.get("extraction") or {}, "review": st.get("review"),
                          "type_confidence": st.get("type_confidence"), "ocr_confidence": st.get("ocr_conf")}
        doc.confidence = (st.get("review") or {}).get("overall_confidence")
        doc.flags = [f["code"] for f in (st.get("review") or {}).get("flags", [])]
        doc.status = "needs_review"
        _record(db, doc, "ready", "ok", 0, "Waiting for your confirmation")
        tr.persist(db)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        log.exception("pipeline failed")
        db.rollback()
        doc = db.get(MedicalDocument, document_id)
        if doc:
            doc.status = "failed"
            doc.error = "Processing failed. Please try again or enter the details manually."
            db.commit()
        _ = exc
    finally:
        db.close()
