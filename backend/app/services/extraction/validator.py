"""Deterministic validation agents that run after extraction.

1. GroundingValidator — every extracted value must be findable in the source text. Values that are
   not found are flagged and heavily down-weighted; reference ranges that are not found are removed
   (we never show an invented range).
2. SafetyReviewer — clinical-safety sanity rules (implausible lab values, unusual strengths,
   unparseable frequencies, duplicates, possible other-patient documents, future dates).
3. ConfidenceScorer — per-item and overall confidence used by the review UI.
"""
from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher

from app.services.medical_knowledge import PLAUSIBLE_LIMITS, STRENGTH_RANGES_MG, canonicalize
from app.services.scheduling import parse_frequency

ATTENTION_THRESHOLD = 0.75


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.%/ ]+", " ", (s or "").lower())).strip()


class Grounder:
    def __init__(self, source: str):
        self.source = norm(source)
        self.numbers = set(re.findall(r"\d+(?:\.\d+)?", self.source))
        # decimal commas ("1,6 mg/dL"); three digits after a comma is a thousands separator, not a decimal
        self.numbers |= {a + "." + b for a, b in re.findall(r"(\d+),(\d{1,2})(?!\d)", source or "")}
        self.words = self.source.split()

    def number(self, value: str | float | None) -> bool:
        if value is None:
            return True
        s = str(value).replace(",", ".").strip("<> ")
        if s in self.numbers:
            return True
        try:
            f = float(s)
            return any(abs(float(n) - f) < 1e-9 for n in self.numbers)
        except ValueError:
            return False

    def text(self, value: str | None, threshold: float = 0.84) -> bool:
        if not value:
            return True
        v = norm(value)
        if not v or v in self.source:
            return True
        n = max(1, len(v.split()))
        best = 0.0
        for i in range(0, max(1, len(self.words) - n + 1)):
            window = " ".join(self.words[i : i + n])
            best = max(best, SequenceMatcher(None, v, window).ratio())
            if best >= threshold:
                return True
        return False


def flag(code: str, message: str, severity: str = "warning", path: str | None = None) -> dict:
    return {"code": code, "message": message, "severity": severity, "path": path}


def _future(iso: str | None) -> bool:
    try:
        return bool(iso) and date.fromisoformat(iso) > date.today()
    except ValueError:
        return False


def validate(doc_type: str, data: dict, source_text: str, *, base_confidence: float, ocr_confidence: float | None,
             patient_name: str | None) -> dict:
    """Mutates `data` (removing ungrounded ranges) and returns the review payload."""
    g = Grounder(source_text)
    flags: list[dict] = []
    items_meta: list[dict] = []
    ocr_factor = 1.0 if ocr_confidence is None else max(0.55, min(1.0, ocr_confidence + 0.1))
    field_conf: dict[str, float] = {}

    def doc_field(name: str, value, kind: str = "text"):  # noqa: ANN001
        if value in (None, "", []):
            field_conf[name] = 0.0
            return
        ok = g.number(value) if kind == "number" else (g.text(value) if kind == "text" else True)
        field_conf[name] = round(base_confidence * ocr_factor * (1 if ok else 0.3), 2)
        if not ok:
            flags.append(flag("not_in_source", f"'{name}' could not be found in the document — please check it.", "high", name))

    if doc_type == "lab_report":
        doc_field("lab_name", data.get("lab_name"))
        doc_field("report_date", data.get("report_date"), "date")
        seen = set()
        for i, t in enumerate(data.get("tests", [])):
            f_item: list[dict] = []
            c = base_confidence * ocr_factor
            vt = str(t.get("value_text") or "")
            numeric = bool(re.search(r"\d", vt))
            if not (g.number(vt) if numeric else g.text(vt, 0.8)):
                f_item.append(flag("not_in_source", "Value not found in the document", "high", f"tests.{i}.value_text"))
                c *= 0.3
            if numeric and not t.get("unit"):
                f_item.append(flag("missing_unit", "No unit printed for this value — check it on the paper report", "info", f"tests.{i}.unit"))
            if not g.text(t.get("name"), 0.8):
                f_item.append(flag("not_in_source", "Test name not found in the document", "high", f"tests.{i}.name"))
                c *= 0.5
            for bound in ("ref_low", "ref_high"):
                if t.get(bound) is not None and not g.number(t.get(bound)):
                    f_item.append(flag("range_removed", "Reference range not printed in the document — removed", "warning", f"tests.{i}.{bound}"))
                    t[bound] = None
            if not t.get("ref_text") and t.get("ref_low") is None and t.get("ref_high") is None:
                f_item.append(flag("no_reference", "No reference range printed — status cannot be determined", "info", f"tests.{i}"))
                c *= 0.9
            elif numeric and t.get("ref_text") and t.get("ref_low") is None and t.get("ref_high") is None:
                f_item.append(flag("complex_reference", "The reference is printed as text, so HealthMate won't mark this high or low — read it on the report", "info", f"tests.{i}"))
            canon = canonicalize(t.get("name", ""))
            try:
                val = float(str(t.get("value_text")).strip("<> ").replace(",", "."))
            except (TypeError, ValueError):
                val = None
            lim = PLAUSIBLE_LIMITS.get(canon)
            if lim and val is not None and not (lim[0] <= val <= lim[1]):
                f_item.append(flag("implausible_value", "This value looks unusual — it may be a reading error. Please compare with the paper report.", "high", f"tests.{i}.value_text"))
                c *= 0.4
            if canon in seen:
                f_item.append(flag("duplicate", "This test appears more than once", "info", f"tests.{i}"))
            seen.add(canon)
            items_meta.append({"index": i, "confidence": round(c, 2), "flags": f_item, "canonical": canon})
        if not data.get("tests"):
            flags.append(flag("no_items", "No test results could be read. Please check the file or enter values manually.", "high"))

    elif doc_type == "prescription":
        doc_field("doctor_name", data.get("doctor_name"))
        doc_field("prescribed_date", data.get("prescribed_date"), "date")
        generics: dict[str, str] = {}
        for i, m in enumerate(data.get("medicines", [])):
            f_item = []
            c = base_confidence * ocr_factor
            if not g.text(m.get("name"), 0.8):
                f_item.append(flag("not_in_source", "Medicine name not found in the document — do not take a medicine you are unsure of.", "high", f"medicines.{i}.name"))
                c *= 0.3
            nums = re.findall(r"\d+(?:\.\d+)?", m.get("strength") or "")
            if nums and not all(g.number(n) for n in nums):
                f_item.append(flag("not_in_source", "Strength not found in the document", "high", f"medicines.{i}.strength"))
                c *= 0.4
            if not m.get("strength"):
                f_item.append(flag("missing_strength", "Strength not written — confirm with your pharmacist", "warning", f"medicines.{i}.strength"))
                c *= 0.85
            fp = parse_frequency(m.get("frequency"))
            if not fp.recognized:
                f_item.append(flag("unclear_frequency", "How often to take this is unclear. Choose the times shown on your prescription or ask your doctor/pharmacist.", "high", f"medicines.{i}.frequency"))
                c *= 0.5
            elif fp.non_daily:
                f_item.append(flag("non_daily", f"This is not taken every day ({m.get('frequency')}). HealthMate only sets daily reminders, so it will be saved "
                                   "without automatic reminders — log it on the day you take it.", "warning", f"medicines.{i}.frequency"))
            elif fp.as_needed:
                f_item.append(flag("as_needed", "Take only when needed — no automatic reminder will be set", "info", f"medicines.{i}.frequency"))
            if not m.get("dosage"):
                f_item.append(flag("missing_dosage", "Dose per intake not written — please confirm", "warning", f"medicines.{i}.dosage"))
                c *= 0.9
            if not m.get("duration_days"):
                f_item.append(flag("missing_duration", "Duration not written — reminders continue until you stop them", "info", f"medicines.{i}.duration_days"))
            parts = [p.strip() for p in (m.get("generic_name") or m.get("name") or "").lower().split("+") if p.strip()]
            st = (m.get("strength") or "").lower()
            doses = re.findall(r"\d+(?:\.\d+)?", st) if st.endswith("mg") else []
            # combination tablets: "Glimepiride + Metformin" with "2/500mg" → check each ingredient against its own range
            pairs = list(zip(parts, doses)) if len(parts) == len(doses) else ([(parts[0], doses[0])] if len(parts) == 1 and len(doses) == 1 else [])
            for ingredient, dose in pairs:
                rng = STRENGTH_RANGES_MG.get(ingredient.split()[0])
                if rng and not (rng[0] <= float(dose) <= rng[1]):
                    f_item.append(flag("unusual_strength", "This strength is unusual for this medicine. Please confirm with your pharmacist before taking it.", "high", f"medicines.{i}.strength"))
                    c *= 0.5
                    break
            shared = [p for p in parts if p in generics]
            if shared:
                f_item.append(flag("duplicate_medicine", f"{generics[shared[0]]} on this prescription also contains {shared[0].title()}. "
                                   "Taking both may double the dose — confirm with your doctor that both are intended.", "warning", f"medicines.{i}"))
            for p in parts:
                generics.setdefault(p, m.get("name") or p)
            if m.get("generic_source") == "dictionary":
                f_item.append(flag("generic_from_dictionary", "Generic name identified from the brand name, not printed on the prescription", "info", f"medicines.{i}.generic_name"))
            items_meta.append({"index": i, "confidence": round(c, 2), "flags": f_item})
        if not data.get("medicines"):
            flags.append(flag("no_items", "No medicines could be read. If the prescription is handwritten or unclear, please verify with your pharmacist or doctor.", "high"))

    elif doc_type in ("diet_advice", "consultation_note"):
        key = "instructions" if doc_type == "diet_advice" else "advice"
        for i, line in enumerate(data.get(key, [])):
            ok = g.text(line, 0.8)
            items_meta.append({"index": i, "confidence": round(base_confidence * ocr_factor * (1 if ok else 0.3), 2),
                               "flags": [] if ok else [flag("not_in_source", "Not found in document", "high", f"{key}.{i}")]})
        doc_field("doctor_name", data.get("doctor_name"))

    elif doc_type == "appointment":
        for fname in ("doctor_name", "clinic", "specialization", "address"):
            doc_field(fname, data.get(fname))
        doc_field("date", data.get("date"), "date")
        doc_field("time", data.get("time"), "date")
        if not data.get("date"):
            flags.append(flag("missing_date", "Appointment date not found — please enter it", "high", "date"))

    # Cross-document checks
    doc_patient = data.get("patient_name")
    if doc_patient and patient_name:
        if SequenceMatcher(None, norm(doc_patient), norm(patient_name)).ratio() < 0.6 and norm(doc_patient.split()[0]) not in norm(patient_name):
            flags.append(flag("patient_mismatch", f"The name on this document ('{doc_patient}') does not match your profile. Make sure it is your document.", "high", "patient_name"))
    for dk in ("report_date", "prescribed_date", "advice_date", "visit_date"):
        if _future(data.get(dk)):
            flags.append(flag("future_date", "This date is in the future — please check", "warning", dk))

    item_confs = [m["confidence"] for m in items_meta]
    doc_confs = [v for v in field_conf.values() if v > 0]
    all_c = item_confs or doc_confs
    overall = round(sum(all_c) / len(all_c), 2) if all_c else 0.0
    if any(f["severity"] == "high" for f in flags):
        overall = round(overall * 0.85, 2)
    return {"items": items_meta, "field_confidence": field_conf, "flags": flags, "overall_confidence": overall,
            "needs_attention": [m["index"] for m in items_meta if m["confidence"] < ATTENTION_THRESHOLD or any(f["severity"] == "high" for f in m["flags"])]}
