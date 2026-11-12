from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.profile import MealTime, save_meals
from app.api.serializers import iso, medicine_out
from app.core.security import require_patient
from app.db.session import get_db
from app.models import MealLog, MealSchedule, MedicineLog, MedicineSchedule, PatientProfile, Prescription, PrescriptionMedicine, ReminderSettings, User
from app.services import scheduling, timeutil
from app.services.audit import audit
from app.services.extraction.commit import PILL_COLORS

router = APIRouter(tags=["medicines"])

Slot = Literal["morning", "afternoon", "evening", "night"]
MealRel = Literal["before_meal", "after_meal", "with_meal", "empty_stomach", "bedtime", "any"]


class MedicineIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    brand_name: str | None = None
    generic_name: str | None = None
    form: str | None = Field(None, max_length=30)
    strength: str | None = Field(None, max_length=40)
    dosage: str | None = Field(None, max_length=60)
    frequency: str | None = Field(None, max_length=40)
    slots: list[Slot] = []
    meal_relation: MealRel = "any"
    as_needed: bool = False
    duration_days: int | None = Field(None, ge=1, le=3650)
    start_date: date | None = None
    instructions: str | None = Field(None, max_length=300)
    stock_count: int | None = Field(None, ge=0, le=10000)
    refill_threshold: int = Field(5, ge=0, le=100)

    @model_validator(mode="after")
    def slots_or_prn(self):  # noqa: ANN201
        if not self.slots and not self.as_needed:
            parsed = scheduling.parse_frequency(self.frequency)
            if parsed.recognized and (parsed.slots or parsed.as_needed):
                self.slots = parsed.slots  # type: ignore[assignment]
                self.as_needed = parsed.as_needed
            else:
                raise ValueError("Choose at least one time of day, or mark as 'only when needed'")
        return self


@router.get("/medicines")
def list_medicines(include_inactive: bool = False, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    q = select(PrescriptionMedicine).where(PrescriptionMedicine.user_id == user.id)
    if not include_inactive:
        q = q.where(PrescriptionMedicine.is_active.is_(True))
    meds = db.scalars(q.order_by(PrescriptionMedicine.created_at.desc())).all()
    return {"items": [medicine_out(m) for m in meds]}


@router.get("/medicines/frequency-preview")
def frequency_preview(frequency: str = "", meal_relation: MealRel = "any", user: User = Depends(require_patient), db: Session = Depends(get_db)):
    fp = scheduling.parse_frequency(frequency)
    meal_times = scheduling.meal_times_for(db, user.id)
    return {"recognized": fp.recognized, "as_needed": fp.as_needed, "note": fp.note,
            "times": [dict(zip(("time", "anchor", "offset", "rule"), scheduling.compute_slot_time(s, meal_relation, meal_times)), slot=s) for s in fp.slots]}


def _apply(med: PrescriptionMedicine, body: MedicineIn) -> None:
    for k, v in body.model_dump().items():
        setattr(med, k, v)
    med.start_date = body.start_date or med.start_date or date.today()
    med.end_date = med.start_date + timedelta(days=body.duration_days - 1) if body.duration_days else None


@router.post("/medicines")
def add_medicine(body: MedicineIn, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    count = db.query(PrescriptionMedicine).filter(PrescriptionMedicine.user_id == user.id).count()
    med = PrescriptionMedicine(user_id=user.id, source="manual", verified=True, color=PILL_COLORS[count % len(PILL_COLORS)], name=body.name)
    _apply(med, body)
    db.add(med)
    db.flush()
    scheduling.regenerate_schedules(db, med)
    audit(db, "medicine.create", actor_id=user.id, resource_type="medicine", resource_id=med.id, meta={"source": "manual"}, request=request)
    db.commit()
    db.refresh(med)
    return {"medicine": medicine_out(med)}


def _owned(db: Session, user: User, med_id: str) -> PrescriptionMedicine:
    med = db.get(PrescriptionMedicine, med_id)
    if not med or med.user_id != user.id:
        raise HTTPException(404, "Medicine not found")
    return med


@router.put("/medicines/{med_id}")
def update_medicine(med_id: str, body: MedicineIn, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    med = _owned(db, user, med_id)
    _apply(med, body)
    med.verified = True  # patient-edited values are patient-verified
    scheduling.regenerate_schedules(db, med)
    audit(db, "medicine.update", actor_id=user.id, resource_type="medicine", resource_id=med.id, request=request)
    db.commit()
    db.refresh(med)
    return {"medicine": medicine_out(med)}


class StockIn(BaseModel):
    stock_count: int = Field(ge=0, le=10000)


@router.patch("/medicines/{med_id}/stock")
def update_stock(med_id: str, body: StockIn, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    med = _owned(db, user, med_id)
    med.stock_count = body.stock_count
    db.commit()
    return {"medicine": medicine_out(med)}


@router.delete("/medicines/{med_id}")
def stop_medicine(med_id: str, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    med = _owned(db, user, med_id)
    med.is_active = False
    scheduling.regenerate_schedules(db, med)
    audit(db, "medicine.deactivate", actor_id=user.id, resource_type="medicine", resource_id=med.id, request=request)
    db.commit()
    return {"ok": True}


@router.get("/medicines/today")
def today(day: date | None = None, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    doses = scheduling.doses_for_day(db, user.id, day)
    by_slot = {s: [d for d in doses if d["slot"] == s] for s in scheduling.SLOTS}
    nxt = next((d for d in doses if d["status"] in ("due", "upcoming")), None)
    prn = db.scalars(select(PrescriptionMedicine).where(PrescriptionMedicine.user_id == user.id, PrescriptionMedicine.is_active.is_(True), PrescriptionMedicine.as_needed.is_(True))).all()
    return {"date": (day or timeutil.local_today(user.profile.timezone if user.profile else None)).isoformat(), "doses": doses, "by_slot": by_slot, "next": nxt,
            "as_needed": [medicine_out(m) for m in prn], "summary": {s: sum(1 for d in doses if d["status"] == s) for s in ("taken", "skipped", "due", "upcoming", "overdue", "missed", "snoozed")}}


class DoseAction(BaseModel):
    schedule_id: str
    scheduled_for: datetime
    action: Literal["taken", "skipped", "snoozed"]


@router.post("/medicines/doses/action")
def dose_action(body: DoseAction, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    sched = db.get(MedicineSchedule, body.schedule_id)
    if not sched or sched.user_id != user.id:
        raise HTTPException(404, "Schedule not found")
    if timeutil.ensure_aware(body.scheduled_for) > timeutil.now_utc() + timedelta(hours=3) and body.action == "taken":
        raise HTTPException(400, "This dose is more than 3 hours away. Please take medicines at the prescribed time.")
    prefs = db.scalar(select(ReminderSettings).where(ReminderSettings.user_id == user.id))
    lg = scheduling.record_dose_action(db, user_id=user.id, schedule=sched, scheduled_for=body.scheduled_for, action=body.action, actor_id=user.id,
                                       snooze_minutes=prefs.snooze_minutes if prefs else 15)
    audit(db, f"dose.{body.action}", actor_id=user.id, resource_type="medicine_log", resource_id=lg.id, request=request)
    db.commit()
    return {"ok": True, "log": {"id": lg.id, "status": lg.status, "snooze_until": iso(lg.snooze_until)}}


@router.get("/medicines/adherence")
def adherence(days: int = 7, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return scheduling.adherence(db, user.id, max(1, min(days, 90)))


@router.get("/medicines/history")
def history(days: int = 14, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    since = timeutil.now_utc() - timedelta(days=max(1, min(days, 180)))
    rows = db.execute(select(MedicineLog, PrescriptionMedicine).join(PrescriptionMedicine, PrescriptionMedicine.id == MedicineLog.medicine_id)
                      .where(MedicineLog.user_id == user.id, MedicineLog.scheduled_for >= since, MedicineLog.status.in_(["taken", "skipped", "missed"]))
                      .order_by(MedicineLog.scheduled_for.desc()).limit(300)).all()
    return {"items": [{"id": lg.id, "medicine": m.name, "strength": m.strength, "status": lg.status, "scheduled_for": iso(lg.scheduled_for), "acted_at": iso(lg.acted_at),
                       "color": m.color} for lg, m in rows]}


@router.get("/prescriptions")
def prescriptions(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rows = db.scalars(select(Prescription).where(Prescription.user_id == user.id).order_by(Prescription.created_at.desc())).all()
    return {"items": [{"id": p.id, "doctor_name": p.doctor_name, "clinic": p.clinic, "prescribed_date": iso(p.prescribed_date), "document_id": p.document_id,
                       "status": p.status, "notes": p.notes, "medicines": [medicine_out(m) for m in p.medicines]} for p in rows]}


# ------------------------------------------------------------------ meals
@router.get("/meals/schedule")
def meal_schedule(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rows = db.scalars(select(MealSchedule).where(MealSchedule.user_id == user.id)).all()
    order = {m: i for i, m in enumerate(["breakfast", "lunch", "snack", "dinner"])}
    return {"items": sorted([{"meal": r.meal, "time": r.time_of_day, "enabled": r.enabled} for r in rows], key=lambda x: order.get(x["meal"], 9)),
            "rules": {"before_meal": "30 min before the meal", "after_meal": "15 min after the meal", "empty_stomach": "60 min before the meal",
                      "bedtime": "90 min after dinner", "max_meal_shift_minutes": scheduling.MAX_MEAL_SHIFT_MINUTES}}


class MealsIn(BaseModel):
    meals: list[MealTime]

    @field_validator("meals")
    @classmethod
    def order_ok(cls, v: list[MealTime]) -> list[MealTime]:
        times = {m.meal: m.time for m in v}
        seq = [times[m] for m in ("breakfast", "lunch", "snack", "dinner") if m in times]
        if seq != sorted(seq):
            raise ValueError("Meal times should be in order: breakfast, lunch, snack, dinner")
        return v


@router.put("/meals/schedule")
def update_meals(body: MealsIn, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    save_meals(db, user.id, body.meals)
    audit(db, "meals.update", actor_id=user.id, resource_type="meal_schedule", request=request)
    db.commit()
    return meal_schedule(user, db)


@router.get("/meals/today")
def meals_today(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    tz = user.profile.timezone if user.profile else None
    day = timeutil.local_today(tz)
    logs = {m.meal: m for m in db.scalars(select(MealLog).where(MealLog.user_id == user.id, MealLog.log_date == day))}
    sched = meal_schedule(user, db)["items"]
    now_hhmm = timeutil.local_now(tz).strftime("%H:%M")
    return {"date": day.isoformat(), "items": [{**s, "status": logs[s["meal"]].status if s["meal"] in logs else ("pending" if s["time"] <= now_hhmm else "upcoming"),
                                                "delayed_until": logs[s["meal"]].delayed_until if s["meal"] in logs else None} for s in sched]}


class MealLogIn(BaseModel):
    meal: Literal["breakfast", "lunch", "snack", "dinner"]
    status: Literal["done", "delayed", "skipped"]
    delayed_until: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


@router.post("/meals/log")
def log_meal(body: MealLogIn, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    tz = user.profile.timezone if user.profile else None
    day = timeutil.local_today(tz)
    if body.status == "delayed" and not body.delayed_until:
        raise HTTPException(422, "Tell us the new meal time")
    row = db.scalar(select(MealLog).where(MealLog.user_id == user.id, MealLog.meal == body.meal, MealLog.log_date == day))
    if not row:
        row = MealLog(user_id=user.id, meal=body.meal, log_date=day, status=body.status)
        db.add(row)
    row.status, row.delayed_until, row.confirmed_at = body.status, body.delayed_until, timeutil.now_utc()
    db.flush()
    affected = [d for d in scheduling.doses_for_day(db, user.id, day) if d.get("advisory")]
    db.commit()
    return {"ok": True, "advisories": [{"medicine": d["name"], "effective_time": d["effective_time"], "advisory": d["advisory"]} for d in affected]}


_ = PatientProfile  # imported for type clarity
