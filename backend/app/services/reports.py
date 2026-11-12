"""Report analysis: deterministic status, plain-language explanations (EN/HI), questions for the
doctor and historical comparison. No diagnosis is ever produced."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MedicalReport, ReportParameter
from app.services.medical_knowledge import KNOWLEDGE

DISCLAIMER_EN = "This explanation is for understanding only. It is not a diagnosis. Please discuss your results with your doctor."
DISCLAIMER_HI = "यह जानकारी केवल समझने के लिए है, यह निदान नहीं है। कृपया अपने परिणाम डॉक्टर से ज़रूर पूछें।"


def to_float(value_text: str | None) -> float | None:
    if value_text is None:
        return None
    try:
        return float(str(value_text).strip().strip("<>").replace(",", "."))
    except ValueError:
        return None


def compute_status(value: float | None, low: float | None, high: float | None) -> str:
    """Deterministic. Uses only the range printed on the report; unknown if no range."""
    if value is None or (low is None and high is None):
        return "unknown"
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "normal"


def explain_parameter(p: ReportParameter, lang: str = "en") -> dict:
    k = KNOWLEDGE.get(p.canonical_name)
    hi = lang == "hi"
    label = (k["label_hi"] if hi else k["label"]) if k else p.name
    if not k:
        what = "आपकी रिपोर्ट में यह जांच है। इसका मतलब डॉक्टर से पूछें।" if hi else "This test is on your report. Ask your doctor what it means for you."
        meaning = ""
    else:
        what = k["what_hi"] if hi else k["what"]
        if p.status == "high":
            meaning = k["high_hi"] if hi else k["high"]
        elif p.status == "low":
            meaning = k["low_hi"] if hi else k["low"]
        elif p.status == "normal":
            meaning = "यह आपकी लैब की सामान्य सीमा में है।" if hi else "This is within your lab's normal range."
        else:
            meaning = "रिपोर्ट में सीमा नहीं दी गई, इसलिए हम इसे सामान्य या असामान्य नहीं बता सकते।" if hi else "No reference range was printed, so we can't say whether it is normal."
    return {"label": label, "what": what, "meaning": meaning}


def build_summary(report: MedicalReport) -> dict:
    """Bilingual summary built only from verified values."""
    out: dict = {}
    for lang in ("en", "hi"):
        hi = lang == "hi"
        abnormal = [p for p in report.parameters if p.status in ("high", "low")]
        unknown = [p for p in report.parameters if p.status == "unknown"]
        findings, questions = [], []
        for p in abnormal:
            ex = explain_parameter(p, lang)
            direction = ("ज़्यादा" if p.status == "high" else "कम") if hi else p.status
            rng = p.ref_text or ""
            findings.append({"parameter": p.name, "canonical": p.canonical_name, "status": p.status,
                             "text": (f"{ex['label']}: {p.value_text} {p.unit or ''} — सीमा {rng} से {direction}। {ex['meaning']}" if hi
                                      else f"{ex['label']} is {direction}: {p.value_text} {p.unit or ''} (lab range {rng}). {ex['meaning']}").strip()})
            k = KNOWLEDGE.get(p.canonical_name)
            if k:
                questions.extend(k["questions_hi"] if hi else k["questions"])
        n = len(report.parameters)
        if hi:
            headline = (f"{n} जांचों में से {len(abnormal)} लैब की सामान्य सीमा से बाहर हैं।" if abnormal else f"सभी {n} जांचें लैब की सामान्य सीमा में हैं।")
        else:
            headline = (f"{len(abnormal)} of {n} results are outside your lab's range." if abnormal else f"All {n} results are within your lab's range.")
        if unknown:
            headline += (f" {len(unknown)} जांचों की सीमा रिपोर्ट में नहीं थी।" if hi else f" {len(unknown)} result(s) had no printed range.")
        generic_q = ["क्या मुझे कोई दोबारा जांच करवानी चाहिए?", "क्या मेरी दवाइयों में बदलाव की ज़रूरत है?"] if hi else ["Do I need any repeat tests, and when?", "Does anything here change my treatment plan?"]
        out[lang] = {"headline": headline, "findings": findings, "questions": list(dict.fromkeys(questions + generic_q))[:8],
                     "disclaimer": DISCLAIMER_HI if hi else DISCLAIMER_EN}
    return out


def parameter_history(db: Session, user_id: str, canonical: str) -> list[dict]:
    rows = db.execute(
        select(ReportParameter, MedicalReport).join(MedicalReport).where(ReportParameter.user_id == user_id, ReportParameter.canonical_name == canonical)
        .order_by(MedicalReport.report_date.asc().nulls_last())
    ).all()
    return [{"date": r.report_date.isoformat() if r.report_date else None, "value": p.value, "value_text": p.value_text, "unit": p.unit,
             "status": p.status, "ref_low": p.ref_low, "ref_high": p.ref_high, "report_id": r.id, "is_sample": r.is_sample} for p, r in rows]


def compare_with_previous(db: Session, report: MedicalReport) -> list[dict]:
    out = []
    for p in report.parameters:
        hist = [h for h in parameter_history(db, report.user_id, p.canonical_name) if h["report_id"] != report.id and h["value"] is not None]
        prior = [h for h in hist if h["date"] and report.report_date and h["date"] < report.report_date.isoformat()]
        if prior and p.value is not None:
            prev = prior[-1]
            delta = round(p.value - prev["value"], 2)
            out.append({"canonical": p.canonical_name, "name": p.name, "previous": prev["value"], "previous_date": prev["date"], "current": p.value,
                        "delta": delta, "direction": "up" if delta > 0 else "down" if delta < 0 else "same", "unit": p.unit})
    return out


def fact_lines(report: MedicalReport) -> list[str]:
    """Verified facts for RAG indexing."""
    head = f"Verified lab report '{report.title}' dated {report.report_date or 'unknown date'} from {report.lab_name or 'unknown lab'}."
    lines = [head]
    for p in report.parameters:
        rng = f" (lab range {p.ref_text})" if p.ref_text else " (no range printed)"
        lines.append(f"{p.name}: {p.value_text} {p.unit or ''}{rng} — status {p.status.upper()}.")
    text = "\n".join(lines)
    from app.services.rag import chunk_text

    return chunk_text(text, size=900, overlap=0)
