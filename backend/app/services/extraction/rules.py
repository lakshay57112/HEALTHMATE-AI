"""Deterministic (rule-based) document classifier and extractors.

Used (a) as the offline demo extractor when no LLM key is configured and (b) as a fallback when an
LLM call fails. Every value comes from a regex match on the source text, so it is grounded by
construction. Anything we cannot match is left empty for the patient to fill in — never guessed.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.services.medical_knowledge import BRAND_TO_GENERIC
from app.services.extraction.schemas import (
    AppointmentExtraction,
    ConsultationExtraction,
    DietAdviceExtraction,
    LabParameter,
    LabReportExtraction,
    PrescriptionExtraction,
    RxMedicine,
)

MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}

# ------------------------------------------------------------------ helpers
DATE_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2})|(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})|(\d{1,2})[\s\-]([A-Za-z]{3,9})[\s\-,]+(\d{4})|([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})"
)


def parse_date(text: str | None) -> str | None:
    if not text:
        return None
    m = DATE_RE.search(text)
    if not m:
        return None
    try:
        if m.group(1):
            return date.fromisoformat(m.group(1)).isoformat()
        if m.group(2):
            d, mo, y = int(m.group(2)), int(m.group(3)), int(m.group(4))
            y = y + 2000 if y < 100 else y
            return date(y, mo, d).isoformat()  # Indian convention dd/mm/yyyy
        if m.group(5):
            mo = MONTHS.get(m.group(6)[:3].lower())
            return date(int(m.group(7)), mo, int(m.group(5))).isoformat() if mo else None
        if m.group(8):
            mo = MONTHS.get(m.group(8)[:3].lower())
            return date(int(m.group(10)), mo, int(m.group(9))).isoformat() if mo else None
    except (ValueError, TypeError):
        return None
    return None


def find_labeled_date(text: str, labels: list[str]) -> str | None:
    for lab in labels:
        m = re.search(rf"(?:{lab})\s*[:\-]?\s*(?P<v>.{{0,30}})", text, re.IGNORECASE)
        if m:
            d = parse_date(m.group("v"))
            if d:
                return d
    return None


def parse_time(text: str) -> str | None:
    m = re.search(r"\b(\d{1,2})[:.](\d{2})\s*(am|pm|AM|PM)?\b", text)
    if not m:
        m2 = re.search(r"\b(\d{1,2})\s*(am|pm|AM|PM)\b", text)
        if not m2:
            return None
        h, mi, ap = int(m2.group(1)), 0, m2.group(2).lower()
    else:
        h, mi, ap = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if 0 <= h < 24 and 0 <= mi < 60:
        return f"{h:02d}:{mi:02d}"
    return None


def find_doctor(text: str) -> str | None:
    m = re.search(r"\bDr\.?[ \t]+([A-Z][a-zA-Z.]+(?:[ \t]+[A-Z][a-zA-Z.]+){0,3})", text)
    return f"Dr. {m.group(1).strip().rstrip('.')}" if m else None


def find_patient_name(text: str) -> str | None:
    m = re.search(r"(?:Patient(?:[ \t]+Name)?|Name)[ \t]*[:\-][ \t]*(?:Mr\.?|Mrs\.?|Ms\.?|Smt\.?|Shri\.?)?[ \t]*([A-Z][a-zA-Z]+(?:[ \t][A-Z][a-zA-Z]+){0,3})", text)
    return m.group(1).strip() if m else None


# ------------------------------------------------------------------ classifier
SIGNALS = {
    "prescription": [r"\brx\b", r"\btab\.?\s", r"\bcap\.?\s", r"\bsyp\.?\s", r"\b\d\s*-\s*\d\s*-\s*\d\b", r"after (food|meals?)", r"before (food|meals?)", r"\bod\b|\bbd\b|\btds\b", r"\bx\s*\d+\s*days\b", r"prescription"],
    "lab_report": [r"reference (range|interval)", r"\bresult\b", r"\bunits?\b", r"specimen|sample", r"laboratory|diagnostics|pathology", r"haemoglobin|hemoglobin|hba1c|cholesterol|creatinine", r"mg/dl|g/dl|mmol/l", r"biological ref"],
    "diet_advice": [r"\bdiet\b", r"\bavoid\b", r"\b(reduce|limit|restrict)\b", r"\bsalt\b|\bsodium\b", r"\bsugar\b|sweets", r"meal plan|dietary|nutrition", r"\binclude\b|\beat more\b"],
    "appointment": [r"appointment", r"booking|booked", r"\btoken\b", r"\bslot\b", r"please arrive|reporting time", r"confirmation"],
    "consultation_note": [r"chief complaint|complaints?", r"history", r"examination|o/e\b", r"impression|assessment", r"advice", r"follow[\s-]?up|review after", r"consultation"],
}


def classify(text: str) -> tuple[str, float, dict[str, int]]:
    low = text.lower()
    scores = {t: sum(1 for p in pats if re.search(p, low)) for t, pats in SIGNALS.items()}
    best = max(scores, key=scores.get)
    total = sum(scores.values()) or 1
    if scores[best] < 2:
        return "other", 0.3, scores
    # Prescriptions often contain advice lines; prefer prescription when drug patterns dominate.
    conf = min(0.97, 0.5 + scores[best] / total)
    return best, round(conf, 2), scores


# ------------------------------------------------------------------ lab reports
NUM = r"[<>]?\s?\d+(?:[.,]\d+)?"
RANGE = rf"(?:{NUM}\s*(?:-|–|to)\s*{NUM}|(?:<|>|<=|>=|≤|≥|up\s*to)\s*\d+(?:\.\d+)?)"
UNIT = r"(?:[a-zA-Zµμ%/][a-zA-Zµμ0-9%/.^*\- ]{0,14}?)"
LAB_LINE = re.compile(
    rf"^\s*(?P<name>[A-Za-z][A-Za-z0-9 ()/,.'\-]{{1,48}}?)\s*[:|]?\s+(?P<value>{NUM})\s*(?P<flag>\b[HL]\b|\(H\)|\(L\)|High|Low)?\s*(?P<unit>{UNIT})?\s*[|]?\s*(?P<ref>{RANGE})?\s*(?P<flag2>\b[HL]\b|High|Low)?\s*$",
    re.IGNORECASE,
)
SKIP_NAMES = re.compile(r"^(page|date|age|sex|gender|phone|mobile|sample|reg|lab no|report|patient|ref\.? by|collected|received|uhid|id|name|tel|pin|time)\b", re.I)


def parse_range(ref: str | None) -> tuple[float | None, float | None]:
    if not ref:
        return None, None
    r = ref.replace(",", ".").strip()
    m = re.match(r"(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)", r)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.match(r"(?:<|<=|≤|up\s*to)\s*(\d+(?:\.\d+)?)", r, re.I)
    if m:
        return None, float(m.group(1))
    m = re.match(r"(?:>|>=|≥)\s*(\d+(?:\.\d+)?)", r)
    if m:
        return float(m.group(1)), None
    return None, None


def extract_lab_report(text: str) -> tuple[LabReportExtraction, dict]:
    tests: list[LabParameter] = []
    group = None
    partial = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.fullmatch(r"[A-Z][A-Z &/()\-]{4,60}", line) and not re.search(r"\d", line):
            group = line.title()
            continue
        if SKIP_NAMES.match(line):
            continue
        m = LAB_LINE.match(line)
        if not m:
            continue
        name = m.group("name").strip(" :-|")
        if len(name) < 2 or SKIP_NAMES.match(name):
            continue
        ref = (m.group("ref") or "").strip() or None
        lo, hi = parse_range(ref)
        unit = (m.group("unit") or "").strip() or None
        if unit and re.fullmatch(r"(to|-)", unit, re.I):
            unit = None
        flag = (m.group("flag") or m.group("flag2") or "").strip("() ").upper()[:1] or None
        if not ref:
            partial += 1
        tests.append(LabParameter(test_group=group, name=name, value_text=m.group("value").replace(" ", ""), unit=unit, ref_text=ref, ref_low=lo, ref_high=hi, flag_in_report=flag))

    lab_name = None
    for line in text.splitlines()[:12]:
        if re.search(r"(laborator(y|ies)|diagnostics?|patholog(y|ies)|labs?\b|hospital|clinic)", line, re.I):
            lab_name = line.strip()[:120]
            break
    title = None
    groups: list[str] = []
    for line in text.splitlines()[:25]:
        ln = line.strip()
        if re.fullmatch(r"[A-Z][A-Z &/()\-]{4,60}", ln) and not re.search(r"\d", ln):
            groups.append(ln.title())  # section heading, not a title
            continue
        if len(ln) >= 8 and re.search(r"\b(report|profile|panel)\b", ln, re.I) and not re.search(r"date|no\.|sample|computer-generated|reference", ln, re.I):
            title = ln[:120]
            break
    if not title:
        for t in tests:
            if t.test_group and t.test_group not in groups:
                groups.append(t.test_group)
        names = [re.sub(r"\s+(Profile|Function|Panel|Test|Tests)$", "", g) for g in groups[:4]]
        title = (", ".join(names[:-1]) + " & " + names[-1] + " tests") if len(names) > 1 else (f"{names[0]} tests" if names else None)
    report_date = find_labeled_date(text, ["report(ed)? (date|on)", "date of report", "collected on", "collection date", "sample date", "date"])
    meta = {"matched_lines": len(tests), "lines_without_reference": partial}
    return LabReportExtraction(lab_name=lab_name, report_date=report_date, patient_name=find_patient_name(text), title=title, tests=tests), meta


# ------------------------------------------------------------------ prescriptions
FORM_RE = r"(?P<form>tab(?:let)?s?|cap(?:sule)?s?|syp|syrup|inj(?:ection)?|drops?|oint(?:ment)?|cream|sachet|inh(?:aler)?)\.?"
STRENGTH_RE = re.compile(r"(\d+(?:\.\d+)?\s*(?:mg|mcg|µg|g|ml|iu|units?|%)(?:\s*/\s*\d+(?:\.\d+)?\s*(?:mg|mcg|ml))?)", re.I)
FREQ_RE = re.compile(r"\b([01½]\s*-\s*[01½]\s*-\s*[01½](?:\s*-\s*[01½])?)\b|\b(OD|BD|BID|TDS|TID|QID|HS|SOS|PRN|once daily|twice daily|thrice daily|at bedtime)\b", re.I)
DURATION_RE = re.compile(r"(?:x|for|×)?\s*(\d+)\s*(day|days|week|weeks|wk|wks|month|months)\b", re.I)
MEAL_PATTERNS = [
    (r"empty stomach", "empty_stomach"),
    (r"before (food|meals?|breakfast|lunch|dinner)|\bac\b|khane se pehle", "before_meal"),
    (r"after (food|meals?|breakfast|lunch|dinner)|\bpc\b|khane ke baad", "after_meal"),
    (r"with (food|meals?)", "with_meal"),
    (r"at bedtime|\bhs\b|before sleep", "bedtime"),
]
FORM_MAP = {"tab": "tablet", "cap": "capsule", "syp": "syrup", "syr": "syrup", "inj": "injection", "dro": "drops", "oin": "ointment", "cre": "cream", "sac": "sachet", "inh": "inhaler"}


def _dosage_from_pattern(freq: str | None, form: str | None) -> str | None:
    if not freq or "-" not in freq:
        return None
    parts = [p.strip() for p in freq.split("-") if p.strip() not in ("0", "")]
    if not parts or len(set(parts)) != 1:
        return None  # uneven doses — let the patient confirm per slot
    unit = form or "unit"
    return f"{parts[0]} {unit}"


def extract_prescription(text: str) -> tuple[PrescriptionExtraction, dict]:
    meds: list[RxMedicine] = []
    lines = [ln.strip() for ln in text.splitlines()]
    med_line = re.compile(rf"^\s*(?:\d+[.)]\s*)?{FORM_RE}\s+(?P<rest>.+)$", re.I)
    for line in lines:
        m = med_line.match(line)
        if not m:
            continue
        rest = m.group("rest")
        form = FORM_MAP.get(m.group("form").lower()[:3], m.group("form").lower())
        strength_m = STRENGTH_RE.search(rest)
        name_part = rest[: strength_m.start()] if strength_m else re.split(r"\s[-—–|]\s|\s{2,}", rest)[0]
        name_part = name_part.strip(" -—–|,")
        brand, generic, gsrc = None, None, "none"
        paren = re.search(r"\(([^)]+)\)", name_part)
        if paren:
            generic = paren.group(1).strip()
            brand = name_part[: paren.start()].strip()
            gsrc = "document"
            name = brand or generic
        else:
            name = name_part
            dict_generic = BRAND_TO_GENERIC.get(name.lower().strip())
            if dict_generic:
                brand, generic, gsrc = name, dict_generic, "dictionary"
        if not name:
            continue
        freq_m = FREQ_RE.search(rest)
        freq = re.sub(r"\s+", "", freq_m.group(1)) if freq_m and freq_m.group(1) else (freq_m.group(2).upper() if freq_m else None)
        meal = "any"
        for pat, rel in MEAL_PATTERNS:
            if re.search(pat, rest, re.I):
                meal = rel
                break
        dur_m = DURATION_RE.search(rest)
        dur_days = dur_text = None
        if dur_m:
            n, unit = int(dur_m.group(1)), dur_m.group(2).lower()
            dur_text = dur_m.group(0).strip()
            dur_days = n * (7 if unit.startswith("w") else 30 if unit.startswith("m") else 1)
        instr = None
        im = re.search(r"\b(continue|stop|do not|avoid|if|only)\b.*$", rest, re.I)
        if im:
            instr = im.group(0).strip()[:200]
        meds.append(RxMedicine(name=name[:120], brand_name=brand, generic_name=generic, generic_source=gsrc, form=form,
                               strength=strength_m.group(1).replace(" ", "") if strength_m else None,
                               dosage=_dosage_from_pattern(freq, form), frequency=freq, meal_relation=meal,
                               duration_days=dur_days, duration_text=dur_text, instructions=instr))
    clinic = None
    for line in lines[:10]:
        if re.search(r"(clinic|hospital|medical cent(er|re)|nursing home|healthcare)", line, re.I):
            clinic = line[:150]
            break
    notes = []
    for line in lines:
        if re.match(r"^(advice|adv|note|notes|instructions?)\s*[:\-]", line, re.I):
            notes.append(re.sub(r"^\w+\s*[:\-]\s*", "", line))
    follow = find_labeled_date(text, ["follow[\\s-]?up( on| date)?", "review on", "next visit", "revisit"])
    return PrescriptionExtraction(doctor_name=find_doctor(text), clinic=clinic, prescribed_date=find_labeled_date(text, ["date"]),
                                  patient_name=find_patient_name(text), notes="; ".join(notes) or None, follow_up_date=follow, medicines=meds), {"matched_lines": len(meds)}


# ------------------------------------------------------------------ diet / appointment / consultation
RESTRICTION_RULES = [
    (r"\b(salt|sodium|namak|pickles?|papad)\b", "low_sodium"),
    (r"\b(sugar|sweets?|mithai|jaggery|cheeni)\b", "low_sugar"),
    (r"\b(fried|oil|ghee|butter|fatty|fat)\b", "low_fat"),
    (r"\b(fibre|fiber|whole grains?|salad|vegetables)\b", "high_fibre"),
    (r"\bprotein\b.{0,30}\b(restrict|limit|reduce|low)|\b(restrict|limit|reduce|low)\b.{0,30}\bprotein\b", "protein_restricted"),
    (r"\b(potassium|banana|coconut water)\b.{0,20}\b(avoid|limit|restrict)|\b(avoid|limit|restrict)\b.{0,30}\b(potassium|banana|coconut water)\b", "low_potassium"),
    (r"\b(fluid|water)\b.{0,20}\b(restrict|limit)\b|\b(restrict|limit)\b.{0,20}\b(fluid|water)\b", "fluid_restricted"),
    (r"\b(red meat|organ meat|purine)\b", "low_purine"),
    (r"\b(high protein|more protein|increase protein)\b", "high_protein"),
]


def restriction_tags(lines: list[str]) -> list[str]:
    tags = []
    for line in lines:
        for pat, tag in RESTRICTION_RULES:
            if re.search(pat, line, re.I) and tag not in tags:
                if tag == "high_fibre" and re.search(r"\b(avoid|less|reduce)\b", line, re.I):
                    continue
                tags.append(tag)
    return tags


def _advice_lines(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        line = raw.strip(" •*-–\t")
        if len(line) < 6:
            continue
        if re.search(r"\b(avoid|reduce|limit|restrict|eat|include|drink|take|prefer|no |less|more|walk|exercise|do not|don't|use|replace|choose|continue|stop)\b", line, re.I):
            out.append(line[:200])
    return out


def extract_diet_advice(text: str) -> tuple[DietAdviceExtraction, dict]:
    lines = _advice_lines(text)
    return DietAdviceExtraction(doctor_name=find_doctor(text), advice_date=find_labeled_date(text, ["date"]), instructions=lines,
                                restrictions=restriction_tags(lines)), {"matched_lines": len(lines)}


SPECIALIZATIONS = r"(cardiologist|endocrinologist|diabetologist|nephrologist|neurologist|physician|general physician|orthopaedic|orthopedic|ophthalmologist|dermatologist|gynaecologist|gynecologist|pulmonologist|gastroenterologist|psychiatrist|ent specialist|dentist|oncologist|urologist|geriatrician)"


def extract_appointment(text: str) -> tuple[AppointmentExtraction, dict]:
    spec = re.search(SPECIALIZATIONS, text, re.I)
    clinic = address = None
    labeled = re.search(r"^\s*address\s*[:\-]\s*(.+)$", text, re.I | re.M)
    if labeled:
        address = labeled.group(1).strip()[:250]
    for line in text.splitlines():
        if not clinic and re.search(r"(clinic|hospital|cent(er|re)\b|healthcare|nursing home)", line, re.I):
            clinic = re.split(r"\s{2,}\|\s{2,}|\s+\|\s+", line.strip())[0][:150]
        if not address and re.search(r"(road|sector|nagar|street|marg|lane)\b", line, re.I):
            address = line.strip()[:250]
    phone = re.search(r"(\+?91[\s-]?)?[6-9]\d{9}|\b0\d{2,4}[\s-]?\d{6,8}\b", text)
    dt = find_labeled_date(text, ["appointment (date|on)", "date of appointment", "date", "on"])
    tm_line = re.search(r"(?:time|at|slot|reporting time)\s*[:\-]?\s*([0-9: ]+\s*(?:am|pm)?)", text, re.I)
    tm = parse_time(tm_line.group(1)) if tm_line else parse_time(text)
    return AppointmentExtraction(doctor_name=find_doctor(text), specialization=spec.group(1).title() if spec else None, clinic=clinic,
                                 address=address, phone=phone.group(0) if phone else None, date=dt, time=tm), {}


def extract_consultation(text: str) -> tuple[ConsultationExtraction, dict]:
    spec = re.search(SPECIALIZATIONS, text, re.I)
    advice = _advice_lines(text)
    diet = [a for a in advice if re.search(r"\b(salt|sugar|diet|food|eat|oil|fried|protein|fruit|vegetable|meal|water)\b", a, re.I)]
    summary = None
    m = re.search(r"(?:impression|assessment|summary|diagnosis)\s*[:\-]\s*(.+)", text, re.I)
    if m:
        summary = m.group(1).strip()[:400]
    clinic = None
    for line in text.splitlines()[:10]:
        if re.search(r"(clinic|hospital|medical cent(er|re))", line, re.I):
            clinic = line.strip()[:150]
            break
    return ConsultationExtraction(doctor_name=find_doctor(text), specialization=spec.group(1).title() if spec else None, clinic=clinic,
                                  visit_date=find_labeled_date(text, ["date", "visit"]), summary=summary, advice=advice, diet_instructions=diet,
                                  restrictions=restriction_tags(diet), follow_up_date=find_labeled_date(text, ["follow[\\s-]?up( on| date)?", "review on", "next visit"])), {}


EXTRACTORS = {
    "lab_report": extract_lab_report,
    "prescription": extract_prescription,
    "diet_advice": extract_diet_advice,
    "appointment": extract_appointment,
    "consultation_note": extract_consultation,
}


def today_iso() -> str:
    return datetime.now().date().isoformat()
