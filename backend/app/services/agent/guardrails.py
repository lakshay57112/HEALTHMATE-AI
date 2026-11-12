"""Deterministic guardrails around the assistant (they run regardless of which model is used).

Input guardrails   : emergency detection, dose-change / prescribing requests, diagnosis requests.
Output guardrails  : block dose-change or prescribing language, soften definitive diagnosis, always
                     append the educational-vs-personal-advice disclaimer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

EMERGENCY_PATTERNS = [
    r"chest pain", r"can'?t breathe|cannot breathe|difficulty breathing|shortness of breath", r"unconscious|fainted|passed out",
    r"stroke|face drooping|slurred speech", r"severe bleeding", r"seizure", r"overdose|took too many", r"suicid|kill myself|end my life|want to die",
    r"सीने में दर्द|छाती में दर्द", r"सांस (नहीं|लेने में)", r"बेहोश", r"आत्महत्या", r"seene mein dard|saans nahi",
]
SELF_HARM = r"suicid|kill myself|end my life|want to die|आत्महत्या"
DOSE_CHANGE_PATTERNS = [
    r"\b(double|increase|decrease|reduce|halve|skip|stop|change|adjust)\b.{0,40}\b(dose|dosage|medicine|tablet|pill|insulin|metformin|mg)\b",
    r"\b(dose|dosage|tablet|medicine)\b.{0,30}\b(double|increase|decrease|reduce|stop|change)\b",
    r"\bshould i (take|stop|start)\b.{0,40}\b(more|less|extra|another)\b",
    r"(दवा|डोज़|खुराक).{0,20}(बढ़ा|घटा|बंद|बदल)", r"dawai.{0,20}(band|badha|kam)",
]
PRESCRIBE_PATTERNS = [r"\b(prescribe|recommend|suggest)\b.{0,30}\b(medicine|drug|tablet|antibiotic|painkiller)\b", r"which (medicine|tablet|drug) should i take",
                      r"कौन सी दवा (लूं|लेनी)"]
DIAGNOSIS_PATTERNS = [
    r"\bdo i have (a |an |any )?(disease|condition|illness|diabetes|cancer|infection|an?a?emia|kidney (disease|problem)|heart (disease|problem)|thyroid problem|[a-z]+itis)\b",
    r"\bam i (diabetic|sick|ill)\b", r"\bdiagnos", r"\bwhat (disease|illness|condition) do i have\b", r"क्या मुझे .{0,20}(बीमारी|डायबिटीज़|शुगर की बीमारी) है",
]

OUTPUT_BLOCK = [
    r"\b(increase|double|decrease|reduce|halve|stop|skip)\b (your|the) (dose|dosage|medicine|metformin|insulin)",
    r"\btake (\d+|two|three|an extra|another|extra) (tablets?|pills?|capsules?|mg|doses?)\b",
    r"\byou should (start|stop) taking\b",
]
OUTPUT_DIAGNOSIS = [(r"\byou have (diabetes|kidney disease|heart disease|anaemia|anemia|hypothyroidism|cancer|[a-z]+itis)\b",
                     "your report shows values that your doctor may want to discuss with you"),
                    (r"\byou are diabetic\b", "your sugar values are outside the lab range"),
                    (r"\bआपको (डायबिटीज़|मधुमेह) है\b", "आपकी शुगर लैब की सीमा से बाहर है")]

DISCLAIMER = {"en": "ℹ️ General information from your records — not medical advice. Please confirm decisions with your doctor.",
              "hi": "ℹ️ यह आपके रिकॉर्ड पर आधारित सामान्य जानकारी है — चिकित्सा सलाह नहीं। निर्णय अपने डॉक्टर से पूछकर लें।"}


@dataclass
class InputCheck:
    emergency: bool = False
    self_harm: bool = False
    dose_change: bool = False
    prescribe: bool = False
    diagnosis: bool = False
    events: list[dict] = field(default_factory=list)


def check_input(text: str) -> InputCheck:
    low = text.lower()
    c = InputCheck()
    c.emergency = any(re.search(p, low) for p in EMERGENCY_PATTERNS)
    c.self_harm = bool(re.search(SELF_HARM, low))
    c.dose_change = any(re.search(p, low) for p in DOSE_CHANGE_PATTERNS)
    c.prescribe = any(re.search(p, low) for p in PRESCRIBE_PATTERNS)
    c.diagnosis = any(re.search(p, low) for p in DIAGNOSIS_PATTERNS)
    for name in ("emergency", "dose_change", "prescribe", "diagnosis"):
        if getattr(c, name):
            c.events.append({"guardrail": f"input_{name}", "decision": "triggered"})
    return c


def emergency_reply(lang: str, self_harm: bool) -> str:
    if self_harm:
        if lang == "hi":
            return ("आप जो महसूस कर रहे हैं वह मायने रखता है, और आपको अकेले इससे नहीं गुज़रना है। कृपया अभी Tele-MANAS हेल्पलाइन 14416 (या 1-800-891-4416) पर कॉल करें, "
                    "या किसी भरोसेमंद व्यक्ति को अपने पास बुलाएं। तुरंत खतरा हो तो 112 पर कॉल करें।")
        return ("I'm really glad you told me. What you're feeling matters, and you don't have to face it alone. Please call Tele-MANAS on 14416 "
                "(or 1-800-891-4416) right now, or ask someone you trust to be with you. If you are in immediate danger, call 112.")
    if lang == "hi":
        return "यह आपातकाल हो सकता है। कृपया तुरंत 112 (आपातकाल) या 108 (एम्बुलेंस) पर कॉल करें, और अपने परिवार/देखभालकर्ता को बताएं। मैं डॉक्टर की जगह नहीं ले सकता।"
    return ("This could be an emergency. Please call 112 (emergency) or 108 (ambulance) now, and let a family member or caretaker know. "
            "I can't assess emergencies — please get medical help immediately.")


def policy_note(check: InputCheck, lang: str) -> str | None:
    if check.dose_change:
        return ("मैं आपकी दवा की खुराक बदलने की सलाह नहीं दे सकता। कृपया अपने डॉक्टर या फार्मासिस्ट से बात करें। मैं आपकी वर्तमान दवा की जानकारी दिखा सकता हूं।" if lang == "hi"
                else "I can't advise changing a dose, skipping or stopping a medicine — please speak to your doctor or pharmacist first. I can show you exactly what was prescribed.")
    if check.prescribe:
        return ("मैं दवा सुझा नहीं सकता। कृपया डॉक्टर से सलाह लें।" if lang == "hi" else "I can't recommend or prescribe medicines. Please ask your doctor or pharmacist.")
    if check.diagnosis:
        return ("मैं निदान नहीं कर सकता, लेकिन आपकी रिपोर्ट के मान समझा सकता हूं।" if lang == "hi"
                else "I can't diagnose conditions, but I can explain what your report values mean and what to ask your doctor.")
    return None


def check_output(text: str, lang: str) -> tuple[str, list[dict]]:
    events = []
    out = text or ""
    for p in OUTPUT_BLOCK:
        if re.search(p, out, re.I):
            out = re.sub(r"[^.\n]*" + p + r"[^.\n]*[.\n]?", "", out, flags=re.I)
            events.append({"guardrail": "output_dose_change", "decision": "removed"})
    for p, repl in OUTPUT_DIAGNOSIS:
        if re.search(p, out, re.I):
            out = re.sub(p, repl, out, flags=re.I)
            events.append({"guardrail": "output_diagnosis", "decision": "softened"})
    out = out.strip()
    if events and not out:
        out = policy_note(InputCheck(dose_change=True), lang) or ""
    return out, events
