"""Deterministic medicine scheduling.

No LLM is involved here. Reminder times are derived from (a) the verified frequency and
meal relation on the prescription and (b) the patient's own meal times, using the explicit
rule table below. Dosage is never modified. If a frequency cannot be parsed, no schedule is
created until the patient picks the slots on the verification screen.

The rule table is intentionally small and conservative and should be reviewed by a clinician
before production use.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CaregiverConnection,
    MealLog,
    MealSchedule,
    MedicineLog,
    MedicineSchedule,
    PatientProfile,
    PrescriptionMedicine,
)
from app.services import timeutil

SLOTS = ["morning", "afternoon", "evening", "night"]
SLOT_TO_MEAL = {"morning": "breakfast", "afternoon": "lunch", "evening": "snack", "night": "dinner"}
SLOT_DEFAULT_TIME = {"morning": "08:00", "afternoon": "14:00", "evening": "18:00", "night": "21:30"}
DEFAULT_MEAL_TIMES = {"breakfast": "08:30", "lunch": "13:00", "snack": "17:00", "dinner": "20:30"}

# Offsets relative to the anchoring meal, in minutes.
MEAL_RULES: dict[str, tuple[int, str]] = {
    "before_meal": (-30, "30 min before {meal}"),
    "after_meal": (15, "15 min after {meal}"),
    "with_meal": (0, "with {meal}"),
    "empty_stomach": (-60, "60 min before {meal} (empty stomach)"),
}
BEDTIME_OFFSET_AFTER_DINNER = 90
# Meal-delay rule: anchored doses follow a delayed meal only within this window.
MAX_MEAL_SHIFT_MINUTES = 120

_FREQ_TABLE: dict[str, list[str]] = {
    "od": ["morning"], "qd": ["morning"], "once daily": ["morning"], "once a day": ["morning"],
    "bd": ["morning", "night"], "bid": ["morning", "night"], "twice daily": ["morning", "night"], "twice a day": ["morning", "night"],
    "tds": ["morning", "afternoon", "night"], "tid": ["morning", "afternoon", "night"], "thrice daily": ["morning", "afternoon", "night"],
    "three times a day": ["morning", "afternoon", "night"],
    "qid": ["morning", "afternoon", "evening", "night"], "four times a day": ["morning", "afternoon", "evening", "night"],
    "hs": ["night"], "at bedtime": ["night"], "bedtime": ["night"], "at night": ["night"],
    "om": ["morning"], "in the morning": ["morning"],
}
_AS_NEEDED = {"sos", "prn", "as needed", "when required", "if needed"}
# Weekly / alternate-day / monthly doses. Only daily reminders exist, so these are saved without automatic
# reminders (like "when needed") rather than being turned into a daily schedule by mistake.
_NON_DAILY = re.compile(r"\b(once a week|once weekly|weekly|every week|once in a week|alternate days?|every other day|once a month|monthly|hafte mein ek baar)\b")


@dataclass
class FrequencyParse:
    slots: list[str]
    as_needed: bool
    recognized: bool
    note: str = ""
    non_daily: bool = False


def parse_frequency(freq: str | None) -> FrequencyParse:
    if not freq:
        return FrequencyParse([], False, False, "No frequency given")
    f = freq.strip().lower()
    if any(k in f for k in _AS_NEEDED):
        return FrequencyParse([], True, True, "Take only when needed — no fixed reminder")
    if _NON_DAILY.search(f):
        return FrequencyParse([], True, True, "Not taken every day — saved without daily reminders", non_daily=True)
    m = re.fullmatch(r"\s*([01½])\s*-\s*([01½])\s*-\s*([01½])(?:\s*-\s*([01½]))?\s*", f)
    if m:
        parts = [p for p in m.groups() if p is not None]
        if len(parts) == 3:
            mapping = ["morning", "afternoon", "night"]
        else:
            mapping = ["morning", "afternoon", "evening", "night"]
        slots = [mapping[i] for i, p in enumerate(parts) if p != "0"]
        return FrequencyParse(slots, False, bool(slots), "" if slots else "Pattern has no doses")
    for key in sorted(_FREQ_TABLE, key=len, reverse=True):
        if re.search(rf"\b{re.escape(key)}\b", f):
            return FrequencyParse(list(_FREQ_TABLE[key]), False, True)
    return FrequencyParse([], False, False, f"Could not understand frequency '{freq}'")


def meal_times_for(db: Session, user_id: str) -> dict[str, str]:
    times = dict(DEFAULT_MEAL_TIMES)
    for ms in db.scalars(select(MealSchedule).where(MealSchedule.user_id == user_id)):
        times[ms.meal] = ms.time_of_day
    return times


def compute_slot_time(slot: str, meal_relation: str, meal_times: dict[str, str]) -> tuple[str, str | None, int, str]:
    """Return (HH:MM, meal_anchor, offset_minutes, rule_description)."""
    meal = SLOT_TO_MEAL[slot]
    if meal_relation == "bedtime" or (slot == "night" and meal_relation == "bedtime"):
        t = timeutil.shift_hhmm(meal_times["dinner"], BEDTIME_OFFSET_AFTER_DINNER)
        return t, "dinner", BEDTIME_OFFSET_AFTER_DINNER, "Bedtime (90 min after dinner)"
    if meal_relation in MEAL_RULES:
        offset, desc = MEAL_RULES[meal_relation]
        return timeutil.shift_hhmm(meal_times[meal], offset), meal, offset, desc.format(meal=meal)
    return SLOT_DEFAULT_TIME[slot], None, 0, f"Default {slot} time"


def regenerate_schedules(db: Session, med: PrescriptionMedicine) -> list[MedicineSchedule]:
    """Rebuild schedules for a verified, active, non-PRN medicine. Existing logs are preserved."""
    for s in list(med.schedules):
        s.active = False
    if not med.verified or not med.is_active or med.as_needed or not med.slots:
        db.flush()
        return []
    meal_times = meal_times_for(db, med.user_id)
    existing = {s.slot: s for s in med.schedules}
    result = []
    for slot in [s for s in SLOTS if s in med.slots]:
        t, anchor, offset, rule = compute_slot_time(slot, med.meal_relation or "any", meal_times)
        sched = existing.get(slot)
        if sched:
            sched.time_of_day, sched.meal_anchor, sched.offset_minutes, sched.rule, sched.active = t, anchor, offset, rule, True
        else:
            sched = MedicineSchedule(medicine=med, user_id=med.user_id, slot=slot, time_of_day=t, meal_anchor=anchor, offset_minutes=offset, rule=rule)
            db.add(sched)
        result.append(sched)
    db.flush()
    return result


def regenerate_all_for_user(db: Session, user_id: str) -> None:
    meds = db.scalars(select(PrescriptionMedicine).where(PrescriptionMedicine.user_id == user_id, PrescriptionMedicine.is_active.is_(True)))
    for med in meds:
        regenerate_schedules(db, med)


def medicine_active_on(med: PrescriptionMedicine, day: date) -> bool:
    if not med.is_active or not med.verified:
        return False
    if med.start_date and day < med.start_date:
        return False
    if med.end_date and day > med.end_date:
        return False
    return True


def escalation_minutes_for(db: Session, user_id: str) -> int:
    vals = db.scalars(
        select(CaregiverConnection.escalation_minutes).where(CaregiverConnection.patient_user_id == user_id, CaregiverConnection.status == "active")
    ).all()
    return min(vals) if vals else 60


def effective_time(sched: MedicineSchedule, meal_logs: dict[str, MealLog], meal_times: dict[str, str]) -> tuple[str, str | None]:
    """Apply the meal-delay rule. Returns (effective HH:MM, advisory note)."""
    if not sched.meal_anchor or sched.offset_minutes < 0:
        # 'Before meal' doses are reminded relative to the planned meal; we never move them later automatically.
        return sched.time_of_day, None
    ml = meal_logs.get(sched.meal_anchor)
    if not ml or ml.status != "delayed" or not ml.delayed_until:
        return sched.time_of_day, None
    planned = meal_times.get(sched.meal_anchor)
    if not planned:
        return sched.time_of_day, None
    shift = timeutil.minutes_between(planned, ml.delayed_until)
    if 0 < shift <= MAX_MEAL_SHIFT_MINUTES:
        return timeutil.shift_hhmm(ml.delayed_until, sched.offset_minutes), f"Moved with your delayed {sched.meal_anchor} (within the {MAX_MEAL_SHIFT_MINUTES}-min rule)"
    if shift > MAX_MEAL_SHIFT_MINUTES:
        return sched.time_of_day, f"Your {sched.meal_anchor} is delayed by more than 2 hours. Please check with your doctor or pharmacist about this dose."
    return sched.time_of_day, None


def doses_for_day(db: Session, user_id: str, day: date | None = None) -> list[dict]:
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == user_id))
    tz = profile.timezone if profile else None
    day = day or timeutil.local_today(tz)
    now = timeutil.now_utc()
    meal_times = meal_times_for(db, user_id)
    meal_logs = {m.meal: m for m in db.scalars(select(MealLog).where(MealLog.user_id == user_id, MealLog.log_date == day))}
    escalation = escalation_minutes_for(db, user_id)

    scheds = db.scalars(
        select(MedicineSchedule).join(PrescriptionMedicine).where(
            MedicineSchedule.user_id == user_id, MedicineSchedule.active.is_(True), PrescriptionMedicine.is_active.is_(True)
        )
    ).all()
    planned_map = {s.id: timeutil.local_dt(day, s.time_of_day, tz) for s in scheds}
    logs = {}
    if scheds:
        for lg in db.scalars(select(MedicineLog).where(MedicineLog.schedule_id.in_([s.id for s in scheds]), MedicineLog.scheduled_for.in_(list(planned_map.values())))):
            logs[(lg.schedule_id, timeutil.ensure_aware(lg.scheduled_for))] = lg

    out = []
    for s in scheds:
        med = s.medicine
        if not medicine_active_on(med, day):
            continue
        planned = planned_map[s.id]
        lg = logs.get((s.id, planned))
        if not lg and planned < timeutil.ensure_aware(s.created_at) - timedelta(minutes=1):
            continue  # dose time had already passed when this schedule was created — never count it as missed
        eff_hhmm, advisory = effective_time(s, meal_logs, meal_times)
        eff_dt = timeutil.local_dt(day, eff_hhmm, tz)
        status = lg.status if lg else None
        if status == "snoozed" and lg and lg.snooze_until:
            eff_dt = timeutil.ensure_aware(lg.snooze_until)
            if now >= eff_dt:
                status = "due"
        if status in (None, "reminded"):
            if now < eff_dt:
                status = "upcoming"
            elif now < eff_dt + timedelta(minutes=escalation):
                status = "due"
            else:
                status = "overdue"
        out.append(
            {
                "schedule_id": s.id,
                "medicine_id": med.id,
                "name": med.name,
                "strength": med.strength,
                "dosage": med.dosage,
                "form": med.form,
                "color": med.color,
                "slot": s.slot,
                "time": s.time_of_day,
                "effective_time": eff_hhmm if not (lg and lg.status == "snoozed") else timeutil.fmt_hhmm(eff_dt.astimezone(timeutil.tz_for(tz)).time()),
                "meal_relation": med.meal_relation,
                "rule": s.rule,
                "advisory": advisory,
                "instructions": med.instructions,
                "scheduled_for": planned.isoformat(),
                "status": status,
                "acted_at": lg.acted_at.isoformat() if lg and lg.acted_at else None,
                "log_id": lg.id if lg else None,
            }
        )
    out.sort(key=lambda d: (d["effective_time"], d["name"]))
    return out


def adherence(db: Session, user_id: str, days: int = 7) -> dict:
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == user_id))
    tz = profile.timezone if profile else None
    today = timeutil.local_today(tz)
    now = timeutil.now_utc()
    scheds = db.scalars(select(MedicineSchedule).where(MedicineSchedule.user_id == user_id, MedicineSchedule.active.is_(True))).all()
    start = today - timedelta(days=days - 1)
    logs = db.scalars(
        select(MedicineLog).where(MedicineLog.user_id == user_id, MedicineLog.scheduled_for >= timeutil.local_dt(start, "00:00", tz))
    ).all()
    log_map = {(lg.schedule_id, timeutil.ensure_aware(lg.scheduled_for)): lg for lg in logs}
    daily = []
    tot_taken = tot_expected = 0
    for i in range(days):
        day = start + timedelta(days=i)
        taken = expected = skipped = missed = 0
        for s in scheds:
            if not medicine_active_on(s.medicine, day):
                continue
            planned = timeutil.local_dt(day, s.time_of_day, tz)
            if planned > now:
                continue
            lg = log_map.get((s.id, planned))
            if not lg and planned < timeutil.ensure_aware(s.created_at) - timedelta(minutes=1):
                continue
            expected += 1
            if lg and lg.status == "taken":
                taken += 1
            elif lg and lg.status == "skipped":
                skipped += 1
            else:
                missed += 1
        tot_taken += taken
        tot_expected += expected
        daily.append({"date": day.isoformat(), "taken": taken, "expected": expected, "skipped": skipped, "missed": missed,
                      "percent": round(100 * taken / expected) if expected else None})
    return {"percent": round(100 * tot_taken / tot_expected) if tot_expected else None, "taken": tot_taken, "expected": tot_expected, "daily": daily}


def record_dose_action(db: Session, *, user_id: str, schedule: MedicineSchedule, scheduled_for: datetime, action: str,
                       actor_id: str, snooze_minutes: int = 15) -> MedicineLog:
    now = timeutil.now_utc()
    scheduled_for = timeutil.ensure_aware(scheduled_for)
    lg = db.scalar(select(MedicineLog).where(MedicineLog.schedule_id == schedule.id, MedicineLog.scheduled_for == scheduled_for))
    if not lg:
        lg = MedicineLog(schedule_id=schedule.id, medicine_id=schedule.medicine_id, user_id=user_id, scheduled_for=scheduled_for, status=action)
        db.add(lg)
    prev = lg.status
    lg.status = action
    lg.acted_at = now
    lg.actor_user_id = actor_id
    lg.snooze_until = now + timedelta(minutes=snooze_minutes) if action == "snoozed" else None
    med = schedule.medicine
    if action == "taken" and prev != "taken" and med.stock_count is not None and med.stock_count > 0:
        med.stock_count -= 1
    db.flush()
    return lg
