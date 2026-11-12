"""Deterministic reminder & escalation engine (runs every REMINDER_TICK_SECONDS inside the API process).

For each patient:
  * dose becomes due            → in-app notification + web push (repeats per settings)
  * dose unconfirmed after the caregiver escalation window → marked missed, patient notified, and
    caregivers *with the missed_medicine_alerts permission and active consent* are alerted
  * stock at/below refill threshold → refill reminder (once per day)
  * appointment within 24 h / within its reminder window → reminder (+ caregivers with permission)
  * 21:00 local → daily summary to caregivers with the daily_summary permission

No LLM is involved; every notification is idempotent via a dedupe key. In production, run this as a
separate worker (e.g. `python -m app.workers.reminders`) instead of inside the web process.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    Appointment,
    MedicineLog,
    MedicineSchedule,
    PatientProfile,
    PrescriptionMedicine,
    ReminderSettings,
    User,
)
from app.services import scheduling, timeutil
from app.services.consent import caregivers_with_permission
from app.services.notify import create_notification

log = logging.getLogger(__name__)


def _hi(user: User) -> bool:
    return user.language == "hi"


def process_patient(db: Session, user: User) -> dict:
    stats = {"due": 0, "missed": 0, "refill": 0, "appointments": 0, "summaries": 0}
    profile = db.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id))
    tz = profile.timezone if profile else None
    now = timeutil.now_utc()
    prefs = db.scalar(select(ReminderSettings).where(ReminderSettings.user_id == user.id)) or ReminderSettings(repeat_count=2, repeat_interval_minutes=10)
    day = timeutil.local_today(tz)
    first = user.full_name.split()[0]

    for dose in scheduling.doses_for_day(db, user.id, day):
        sched = db.get(MedicineSchedule, dose["schedule_id"])
        planned = timeutil.ensure_aware(datetime.fromisoformat(dose["scheduled_for"]))
        med_label = f"{dose['name']} {dose['strength'] or ''}".strip()
        if dose["status"] == "due":
            eff = timeutil.local_dt(day, dose["effective_time"], tz)
            for n in range(max(1, prefs.repeat_count or 1)):
                if now >= eff + timedelta(minutes=n * (prefs.repeat_interval_minutes or 10)):
                    title = "दवा का समय" if _hi(user) else "Time for your medicine"
                    body = (f"{med_label} — {dose['dosage'] or ''} लेने का समय हो गया है।" if _hi(user) else f"Please take {med_label} ({dose['dosage'] or 'as prescribed'}).")
                    if create_notification(db, user.id, "medicine_due", title, body, severity="info",
                                           data={"schedule_id": sched.id, "scheduled_for": dose["scheduled_for"], "url": "/app/medicines/schedule"},
                                           dedupe_key=f"due:{sched.id}:{dose['scheduled_for']}:{n}"):
                        stats["due"] += 1
            lg = db.scalar(select(MedicineLog).where(MedicineLog.schedule_id == sched.id, MedicineLog.scheduled_for == planned))
            if not lg:
                db.add(MedicineLog(schedule_id=sched.id, medicine_id=sched.medicine_id, user_id=user.id, scheduled_for=planned, status="reminded", reminder_sent_at=now))
        elif dose["status"] == "overdue":
            lg = db.scalar(select(MedicineLog).where(MedicineLog.schedule_id == sched.id, MedicineLog.scheduled_for == planned))
            if lg and lg.status in ("taken", "skipped", "missed"):
                continue
            if not lg:
                lg = MedicineLog(schedule_id=sched.id, medicine_id=sched.medicine_id, user_id=user.id, scheduled_for=planned, status="missed")
                db.add(lg)
            lg.status = "missed"
            lg.caregiver_alerted_at = now
            stats["missed"] += 1
            create_notification(db, user.id, "medicine_missed", "दवा छूट गई" if _hi(user) else "Missed medicine",
                                f"{med_label} ({dose['time']}) की पुष्टि नहीं हुई।" if _hi(user) else f"{med_label} at {dose['time']} was not confirmed.",
                                severity="warning", data={"url": "/app/medicines/schedule"}, dedupe_key=f"missed:{sched.id}:{dose['scheduled_for']}")
            for conn in caregivers_with_permission(db, user.id, "missed_medicine_alerts"):
                create_notification(db, conn.caregiver_user_id, "caregiver_missed_medicine", f"{first} may have missed a medicine",
                                    f"{first} has not confirmed {med_label} scheduled at {dose['time']}. You may want to check in.",
                                    severity="warning", data={"patient_id": user.id, "url": f"/caregiver?patient={user.id}"},
                                    dedupe_key=f"cg-missed:{conn.id}:{sched.id}:{dose['scheduled_for']}")

    if prefs.refill_alerts is not False:
        for med in db.scalars(select(PrescriptionMedicine).where(PrescriptionMedicine.user_id == user.id, PrescriptionMedicine.is_active.is_(True),
                                                                 PrescriptionMedicine.stock_count.is_not(None))):
            if med.stock_count <= med.refill_threshold:
                if create_notification(db, user.id, "refill", "Refill reminder", f"Only {med.stock_count} {med.form or 'dose'}(s) of {med.name} left. Please arrange a refill.",
                                       severity="warning", data={"medicine_id": med.id, "url": "/app/medicines"}, dedupe_key=f"refill:{med.id}:{day}"):
                    stats["refill"] += 1

    for appt in db.scalars(select(Appointment).where(Appointment.user_id == user.id, Appointment.status == "upcoming", Appointment.scheduled_at > now,
                                                     Appointment.scheduled_at <= now + timedelta(hours=24))):
        at = timeutil.ensure_aware(appt.scheduled_at)
        local = at.astimezone(timeutil.tz_for(tz)).strftime("%d %b, %I:%M %p")
        windows = [("24h", timedelta(hours=24)), ("soon", timedelta(minutes=appt.reminder_minutes_before or 120))]
        for key, delta in windows:
            if now >= at - delta:
                if create_notification(db, user.id, "appointment", "Upcoming appointment", f"{appt.doctor_name} — {local}" + (f" at {appt.clinic}" if appt.clinic else ""),
                                       data={"appointment_id": appt.id, "url": "/app/appointments"}, dedupe_key=f"appt:{appt.id}:{key}"):
                    stats["appointments"] += 1
                for conn in caregivers_with_permission(db, user.id, "appointment_alerts"):
                    create_notification(db, conn.caregiver_user_id, "caregiver_appointment", f"{first}'s appointment",
                                        f"{first} has an appointment with {appt.doctor_name} on {local}.",
                                        data={"patient_id": user.id, "url": f"/caregiver?patient={user.id}"}, dedupe_key=f"cg-appt:{conn.id}:{appt.id}:{key}")

    local_now = timeutil.local_now(tz)
    if local_now.hour >= 21:
        conns = caregivers_with_permission(db, user.id, "daily_summary")
        if conns:
            doses = scheduling.doses_for_day(db, user.id, day)
            taken = sum(1 for d in doses if d["status"] == "taken")
            missed = sum(1 for d in doses if d["status"] in ("missed", "overdue"))
            for conn in conns:
                if create_notification(db, conn.caregiver_user_id, "caregiver_daily_summary", f"Daily summary for {first}",
                                       f"Medicines: {taken} of {len(doses)} taken" + (f", {missed} missed" if missed else "") + ".",
                                       data={"patient_id": user.id, "url": f"/caregiver?patient={user.id}"}, dedupe_key=f"daily:{conn.id}:{day}", push=False):
                    stats["summaries"] += 1
    return stats


def tick() -> dict:
    db = SessionLocal()
    totals = {"patients": 0}
    try:
        patients = db.scalars(select(User).where(User.role == "patient", User.is_active.is_(True))).all()
        for user in patients:
            try:
                stats = process_patient(db, user)
                db.commit()
                totals["patients"] += 1
                for k, v in stats.items():
                    totals[k] = totals.get(k, 0) + v
            except Exception:  # noqa: BLE001
                db.rollback()
                log.exception("reminder tick failed for a patient")
    finally:
        db.close()
    return totals


async def run_forever() -> None:
    interval = get_settings().reminder_tick_seconds
    log.info("Reminder engine started (every %ss)", interval)
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:  # noqa: BLE001
            log.exception("reminder engine tick error")
        await asyncio.sleep(interval)
