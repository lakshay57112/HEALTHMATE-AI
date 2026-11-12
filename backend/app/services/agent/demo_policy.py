"""Deterministic planner used when no LLM key is configured ("demo mode").

It plugs into the same harness as a real model: it emits tool calls, receives tool results, then
writes the final answer from templates. This keeps the whole agent loop (hooks, guardrails, taint
gating, tracing, UI events) testable offline. It is clearly labelled "rule-based demo" in the UI.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

from app.services.extraction.rules import find_doctor, parse_date, parse_time
from app.services.llm import LLMResponse, ToolCall

MEAL = {"en": {"before_meal": "before food", "after_meal": "after food", "with_meal": "with food", "empty_stomach": "on an empty stomach", "bedtime": "at bedtime", "any": ""},
        "hi": {"before_meal": "खाने से पहले", "after_meal": "खाने के बाद", "with_meal": "खाने के साथ", "empty_stomach": "खाली पेट", "bedtime": "सोने से पहले", "any": ""}}
STATUS = {"en": {"taken": "taken ✓", "upcoming": "upcoming", "due": "due now", "overdue": "not confirmed yet", "missed": "missed", "skipped": "skipped", "snoozed": "snoozed"},
          "hi": {"taken": "ली गई ✓", "upcoming": "आने वाली", "due": "अभी लेनी है", "overdue": "पुष्टि बाकी", "missed": "छूट गई", "skipped": "छोड़ी", "snoozed": "थोड़ी देर बाद"}}
STAT_WORD = {"en": {"high": "high", "low": "low"}, "hi": {"high": "ज़्यादा", "low": "कम"}}
PARAM_WORDS = r"(hba1c|a1c|cholesterol|ldl|hdl|triglycerides?|creatinine|urea|tsh|thyroid|haemoglobin|hemoglobin|vitamin d|vitamin b12|b12|sugar|glucose|uric acid|sodium|potassium|शुगर|कोलेस्ट्रॉल|हीमोग्लोबिन)"


def _call(name: str, args: dict | None = None, i: int = 0) -> ToolCall:
    return ToolCall(id=f"demo_{name}_{i}", name=name, arguments=args or {})


def _relative_date(text: str) -> str | None:
    low = text.lower()
    today = date.today()
    if "day after tomorrow" in low or "parson" in low:
        return (today + timedelta(days=2)).isoformat()
    if "tomorrow" in low or "kal" in low or "कल" in low:
        return (today + timedelta(days=1)).isoformat()
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, d in enumerate(days):
        if d in low:
            delta = (i - today.weekday()) % 7 or 7
            return (today + timedelta(days=delta)).isoformat()
    return parse_date(text)


def plan(message: str, tools_available: set[str]) -> list[ToolCall]:
    m = message.lower()
    calls: list[ToolCall] = []
    # Proposals (writes) — only when available (the harness hides them after taint)
    bp = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", m)
    if re.search(r"\b(log|record|add|note|save|my)\b", m) and "propose_measurement_log" in tools_available:
        if bp and re.search(r"\b(bp|blood pressure|pressure)\b", m):
            return [_call("propose_measurement_log", {"kind": "blood_pressure", "value": float(bp.group(1)), "value2": float(bp.group(2)), "context": "resting"})]
        g = re.search(r"\b(sugar|glucose)\b[^\d]{0,20}(\d{2,3})", m)
        if g:
            return [_call("propose_measurement_log", {"kind": "glucose", "value": float(g.group(2)), "context": "fasting" if "fasting" in m else "random"})]
        w = re.search(r"\bweight\b[^\d]{0,15}(\d{2,3}(?:\.\d)?)", m)
        if w:
            return [_call("propose_measurement_log", {"kind": "weight", "value": float(w.group(1))})]
    if re.search(r"\b(book|add|schedule|set up|fix)\b.{0,30}\bappointment\b", m) and "propose_appointment" in tools_available:
        d = _relative_date(message)
        if d:
            return [_call("propose_appointment", {"doctor_name": find_doctor(message) or "Doctor", "date": d, "time": parse_time(message) or "10:00"})]
    if re.search(r"\b(remember|yaad rakh)|याद रख", m) and "remember_preference" in tools_available:
        content = re.sub(r"^.*?(remember( that)?|yaad rakh(na|o)?|याद रखना|याद रखो)\s*", "", message, flags=re.I).strip(" .:") or message
        return [_call("remember_preference", {"content": content[:200]})]

    if re.search(r"\b(adherence|miss|missed|skip|skipped|how (am i|have i been) doing|kitni dawai)\b|छूट", m):
        calls.append(_call("get_adherence", {"days": 7}))
    if re.search(r"\b(medicine|medicines|meds|tablet|tablets|pill|pills|dawai|dawa|dose)\b|दवा|दवाई|गोली", m):
        if re.search(r"\b(all|list|which|what are my|kaun si)\b|सभी|कौन", m) and not re.search(r"\b(today|aaj|now|next)\b|आज|अभी", m):
            calls.append(_call("get_medicine_list"))
        else:
            calls.append(_call("get_todays_medicines"))
    if re.search(r"\b(appointment|appointments|doctor visit|next visit|checkup|check-up)\b|अपॉइंटमेंट|डॉक्टर से मिलना", m):
        calls.append(_call("get_upcoming_appointments", {"limit": 3}))
    pm = re.search(PARAM_WORDS, m)
    if re.search(r"\b(report|reports|blood test|test result|results|lab)\b|रिपोर्ट|जांच", m) or (pm and not re.search(r"\b(diet|food|eat)\b", m)):
        if pm and re.search(r"\b(trend|over time|history|improv\w*|compare|change\w*|better|worse|pichl\w*|behtar|sudhar\w*|pehle|kam hua|badha)\b|पहले|सुधार|बेहतर", m):
            calls.append(_call("get_parameter_history", {"parameter": pm.group(1)}))
        else:
            calls.append(_call("get_latest_report_summary"))
    if re.search(r"\b(diet|food|eat|eating|meal|meals|khana|recipe|breakfast|lunch|dinner|nutrition)\b|खाना|खाने|आहार", m):
        calls.append(_call("get_diet_instructions"))
    if re.search(r"\b(bp|blood pressure|weight|heart rate|pulse|readings?)\b", m) and not calls:
        kind = "blood_pressure" if re.search(r"\b(bp|blood pressure)\b", m) else "weight" if "weight" in m else "heart_rate" if re.search(r"heart|pulse", m) else None
        calls.append(_call("get_health_measurements", {"kind": kind, "days": 30}))
    if re.search(r"\b(what is|what does|meaning of|mean|explain)\b|क्या होता|मतलब", m) and pm and not calls:
        calls.append(_call("explain_medical_term", {"term": pm.group(1)}))
    if not calls or re.search(r"\b(doctor (said|say|recommend|advise)|note|notes|prescription said|document)\b", m):
        calls.append(_call("search_health_records", {"query": message[:200]}))
    # de-duplicate, keep order, cap at 3
    seen, out = set(), []
    for i, c in enumerate(calls):
        if c.name not in seen:
            seen.add(c.name)
            out.append(ToolCall(id=f"demo_{c.name}_{i}", name=c.name, arguments=c.arguments))
    return out[:3]


# ------------------------------------------------------------------ answer composition
def _fmt_time(hhmm: str) -> str:
    h, mi = map(int, hhmm.split(":"))
    return f"{(h % 12) or 12}:{mi:02d} {'AM' if h < 12 else 'PM'}"


def compose(results: list[tuple[str, dict]], lang: str) -> str:
    hi = lang == "hi"
    parts: list[str] = []
    for name, r in results:
        if "error" in r:
            parts.append("मैं यह जानकारी अभी नहीं देख सका।" if hi else "I couldn't look that up just now.")
            continue
        if name == "get_todays_medicines":
            doses = r.get("doses", [])
            if not doses:
                if r.get("active_medicines"):
                    parts.append(f"आज के लिए कोई और खुराक बाकी नहीं है। आपकी {r['active_medicines']} सक्रिय दवाइयां कल से अपने समय पर याद दिलाई जाएंगी।" if hi
                                 else f"From your records: there are no more doses scheduled for today. Reminders for your {r['active_medicines']} active medicine(s) continue at their usual times.")
                else:
                    parts.append("आज के लिए कोई दवा निर्धारित नहीं है।" if hi else "From your records: no medicines are scheduled for today.")
                continue
            head = f"आपके रिकॉर्ड के अनुसार आज {len(doses)} खुराक हैं:" if hi else f"From your records, you have {len(doses)} doses today:"
            lines = [f"• {_fmt_time(d['effective_time'])} — {d['name']} {d['strength'] or ''} ({d['dosage'] or ('जैसा लिखा है' if hi else 'as prescribed')})"
                     f"{', ' + MEAL[lang][d['meal_relation']] if MEAL[lang].get(d['meal_relation']) else ''} — {STATUS[lang].get(d['status'], d['status'])}" for d in doses]
            nxt = r.get("next")
            tail = (f"\nअगली दवा: {nxt['name']} {_fmt_time(nxt['effective_time'])} पर।" if hi else f"\nNext: {nxt['name']} at {_fmt_time(nxt['effective_time'])}.") if nxt else ""
            parts.append(head + "\n" + "\n".join(lines) + tail)
        elif name == "get_medicine_list":
            meds = r.get("medicines", [])
            if not meds:
                parts.append("कोई सक्रिय दवा नहीं मिली।" if hi else "You have no active medicines saved yet.")
                continue
            lines = [f"• {m['name']} {m['strength'] or ''} — {m['dosage'] or ''} {m['frequency'] or ''} {MEAL[lang].get(m['meal_relation'], '')}".rstrip() + (f" ({'तक' if hi else 'until'} {m['end']})" if m.get("end") else "") for m in meds]
            parts.append(("आपकी सक्रिय दवाइयां:\n" if hi else "From your records, your active medicines:\n") + "\n".join(lines))
        elif name == "get_adherence":
            if r.get("percent") is None:
                parts.append("अभी पर्याप्त डेटा नहीं है।" if hi else "There isn't enough history yet to calculate adherence.")
            else:
                parts.append(f"पिछले {r['days']} दिनों में आपने {r['expected']} में से {r['taken']} खुराक लीं ({r['percent']}%)।" if hi
                             else f"In the last {r['days']} days you took {r['taken']} of {r['expected']} doses ({r['percent']}%).")
        elif name == "get_upcoming_appointments":
            ap = r.get("appointments", [])
            if not ap:
                parts.append("कोई आने वाला अपॉइंटमेंट नहीं है।" if hi else "You have no upcoming appointments saved.")
            else:
                a = ap[0]
                spec = f" ({a['specialization']})" if a.get("specialization") else ""
                where = f", {a['clinic']}" if a.get("clinic") else ""
                parts.append(f"आपका अगला अपॉइंटमेंट {a['doctor']}{spec} के साथ {a['when']}{where} है।" if hi else f"Your next appointment is with {a['doctor']}{spec} on {a['when']}{where}.")
        elif name == "get_latest_report_summary":
            rep = r.get("report")
            if not rep:
                parts.append("अभी कोई सत्यापित रिपोर्ट नहीं है। रिपोर्ट अपलोड करें।" if hi else "You don't have a verified report yet. Upload one from Medical Reports.")
                continue
            from app.services.medical_knowledge import KNOWLEDGE

            ab = [p for p in rep["parameters"] if p["status"] in ("high", "low")]
            sample = (" (नमूना डेटा)" if hi else " (sample data)") if rep.get("is_sample") else ""
            head = (f"आपकी नवीनतम रिपोर्ट '{rep['title']}' ({rep['date'] or ''}){sample}: {len(rep['parameters'])} में से {len(ab)} मान लैब की सीमा से बाहर हैं।" if hi
                    else f"From your records — '{rep['title']}' ({rep['date'] or 'undated'}){sample}: {len(ab)} of {len(rep['parameters'])} results are outside the lab's range.")
            lines = []
            for p in ab[:5]:
                k = KNOWLEDGE.get(p["canonical"], {})
                expl = k.get(f"{p['status']}_hi" if hi else p["status"], "")
                lines.append(f"• {p['name']}: {p['value']} {p['unit'] or ''} ({'सीमा' if hi else 'range'} {p['range'] or '—'}) — {STAT_WORD[lang][p['status']]}. {expl}")
            q = "\nडॉक्टर से पूछें: क्या इन मानों के लिए कोई बदलाव या दोबारा जांच ज़रूरी है?" if hi else "\nAsk your doctor: do any of these need a change in treatment or a repeat test?"
            parts.append(head + ("\n" + "\n".join(lines) if lines else "") + (q if ab else ""))
        elif name == "get_parameter_history":
            h = [x for x in r.get("history", []) if x["value"] is not None]
            if not h:
                parts.append("इस जांच का कोई इतिहास नहीं मिला।" if hi else f"I couldn't find any {r.get('label')} results in your verified reports.")
            else:
                seq = " → ".join(f"{x['value_text']} ({x['date'] or '?'})" for x in h[-5:])
                trend = ""
                if len(h) >= 2:
                    d = round(h[-1]["value"] - h[-2]["value"], 2)
                    trend = (f" पिछली बार से {abs(d)} {'बढ़ा' if d > 0 else 'घटा'}।" if hi else f" That's {'up' if d > 0 else 'down'} {abs(d)} from last time.") if d else ""
                parts.append(f"{r.get('label')}: {seq}.{trend}")
        elif name == "get_diet_instructions":
            lines = []
            if r.get("doctor_instructions"):
                lines.append(("डॉक्टर की सलाह:\n" if hi else "Your doctor advised:\n") + "\n".join(f"• {x}" for x in r["doctor_instructions"][:5]))
            restr = list(r.get("restrictions", {}).keys()) + list(r.get("report_based_preferences", {}).keys())
            if restr:
                from app.services.nutrition import RESTRICTION_LABELS

                lines.append(("आपके भोजन योजना के नियम: " if hi else "Your meal plan follows: ") + ", ".join(RESTRICTION_LABELS.get(x, x) for x in restr) + ".")
            for b in r.get("safety_blocks", {}).values():
                lines.append("⚠️ " + b)
            meals = r.get("todays_meals") or {}
            if meals:
                lines.append(("आज के भोजन: " if hi else "Today's plan: ") + "; ".join(f"{k}: {', '.join(v)}" for k, v in meals.items() if v) + ".")
            parts.append("\n".join(lines) or ("अभी कोई आहार सलाह सहेजी नहीं गई है।" if hi else "No diet advice has been saved yet. Upload your doctor's diet advice to personalise your plan."))
        elif name == "get_health_measurements":
            ms = r.get("measurements", [])
            if not ms:
                parts.append("कोई रीडिंग नहीं मिली।" if hi else "No readings found for that period.")
            else:
                lines = [f"• {x['date']}: {x['kind'].replace('_', ' ')} {x['value']:g}{'/' + format(x['value2'], 'g') if x.get('value2') else ''} {x['unit']}" + (" (sample)" if x.get("sample_data") else "") for x in ms[:5]]
                parts.append(("हाल की रीडिंग:\n" if hi else "Your recent readings:\n") + "\n".join(lines))
        elif name == "search_health_records":
            res = r.get("results", [])
            if not res:
                parts.append("आपके दस्तावेज़ों में इससे जुड़ी जानकारी नहीं मिली।" if hi else "I couldn't find anything about that in your documents.")
                continue
            lines = []
            for x in res[:2]:
                snippet = re.sub(r"\s+", " ", x["text"])[:220]
                if x.get("possible_injection"):
                    lines.append(f"• {x['source']}: " + ("(इस दस्तावेज़ में असामान्य निर्देश थे जिन्हें अनदेखा किया गया)" if hi else "(this document contained unusual instructions, which I ignored)"))
                else:
                    lines.append(f"• {x['source']}{'' if x['verified'] else (' (असत्यापित)' if hi else ' (unverified)')}: “{snippet}…”")
            parts.append(("आपके दस्तावेज़ों में मिला:\n" if hi else "Here's what I found in your documents:\n") + "\n".join(lines))
        elif name == "explain_medical_term":
            if not r.get("found"):
                parts.append("इस शब्द की जानकारी मेरे पास नहीं है; डॉक्टर से पूछें।" if hi else "I don't have a simple explanation for that term — please ask your doctor.")
            else:
                parts.append((f"सामान्य जानकारी: {r['what']} ज़्यादा होने पर: {r['if_high']} कम होने पर: {r['if_low']}" if hi
                              else f"General information: {r['what']} If high: {r['if_high']} If low: {r['if_low']}"))
        elif name in ("propose_appointment", "propose_measurement_log"):
            if r.get("proposal_id"):
                parts.append(f"मैंने यह तैयार किया है: {r['summary']}। सहेजने के लिए नीचे 'Approve' दबाएं।" if hi
                             else f"I've prepared this for you: {r['summary']}. Tap Approve below to save it — nothing is saved until you do.")
        elif name == "remember_preference":
            parts.append("ठीक है, मैं यह याद रखूंगा।" if hi else "Okay — I'll remember that.")
    return "\n\n".join(p for p in parts if p).strip()


class DemoPlanner:
    name = "demo"
    model = "rule-based-demo"

    def next(self, messages: list[dict], tools_available: set[str], lang: str) -> LLMResponse:
        # Collect tool results produced in the current turn (after the last user message).
        last_user = max(i for i, m in enumerate(messages) if m["role"] == "user")
        turn = messages[last_user + 1 :]
        results = []
        for m in turn:
            if m["role"] == "tool":
                try:
                    payload = json.loads(m["raw"])
                except (KeyError, json.JSONDecodeError):
                    payload = {}
                results.append((m["name"], payload))
        if not results:
            return LLMResponse(None, plan(messages[last_user]["content"], tools_available), {}, self.model)
        return LLMResponse(compose(results, lang) or ("मैं इसमें मदद नहीं कर सका।" if lang == "hi" else "I'm not sure I can help with that. Try asking about your medicines, reports, appointments or diet."),
                           [], {}, self.model)
