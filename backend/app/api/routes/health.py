"""Appointments, measurements, daily check-ins and the health timeline."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serializers import appointment_out, iso, measurement_out
from app.core.security import require_patient
from app.db.session import get_db
from app.models import (
    Appointment,
    DailyCheckin,
    HealthMeasurement,
    MedicalDocument,
    MedicalReport,
    MedicineLog,
    NutritionPlan,
    Prescription,
    User,
)
from app.services import timeutil
from app.services.audit import audit

router = APIRouter(tags=["health"])


# ------------------------------------------------------------------ appointments
class AppointmentIn(BaseModel):
    doctor_name: str = Field(min_length=2, max_length=120)
    specialization: str | None = Field(None, max_length=120)
    clinic: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=300)
    phone: str | None = Field(None, max_length=30)
    scheduled_at: datetime
    notes: str | None = Field(None, max_length=2000)
    consultation_summary: str | None = Field(None, max_length=4000)
    reminder_minutes_before: int = Field(120, ge=0, le=2880)
    prescription_id: str | None = None
    document_id: str | None = None
    status: Literal["upcoming", "completed", "cancelled"] = "upcoming"


@router.get("/appointments")
def list_appointments(scope: Literal["upcoming", "past", "all"] = "all", q: str | None = None, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    query = select(Appointment).where(Appointment.user_id == user.id)
    now = timeutil.now_utc()
    if scope == "upcoming":
        query = query.where(Appointment.scheduled_at >= now, Appointment.status == "upcoming").order_by(Appointment.scheduled_at.asc())
    elif scope == "past":
        query = query.where((Appointment.scheduled_at < now) | (Appointment.status != "upcoming")).order_by(Appointment.scheduled_at.desc())
    else:
        query = query.order_by(Appointment.scheduled_at.desc())
    rows = db.scalars(query).all()
    if q:
        ql = q.lower()
        rows = [a for a in rows if ql in a.doctor_name.lower() or ql in (a.specialization or "").lower() or ql in (a.clinic or "").lower()]
    return {"items": [appointment_out(a) for a in rows]}


@router.post("/appointments")
def create_appointment(body: AppointmentIn, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    a = Appointment(user_id=user.id, **body.model_dump(), source="manual")
    db.add(a)
    db.flush()
    audit(db, "appointment.create", actor_id=user.id, resource_type="appointment", resource_id=a.id, request=request)
    db.commit()
    return {"appointment": appointment_out(a)}


def _appt(db: Session, user: User, appt_id: str) -> Appointment:
    a = db.get(Appointment, appt_id)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Appointment not found")
    return a


@router.put("/appointments/{appt_id}")
def update_appointment(appt_id: str, body: AppointmentIn, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    a = _appt(db, user, appt_id)
    for k, v in body.model_dump().items():
        setattr(a, k, v)
    audit(db, "appointment.update", actor_id=user.id, resource_type="appointment", resource_id=a.id, request=request)
    db.commit()
    return {"appointment": appointment_out(a)}


@router.delete("/appointments/{appt_id}")
def delete_appointment(appt_id: str, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    a = _appt(db, user, appt_id)
    db.delete(a)
    audit(db, "appointment.delete", actor_id=user.id, resource_type="appointment", resource_id=appt_id, request=request)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ measurements
UNITS = {"blood_pressure": "mmHg", "glucose": "mg/dL", "heart_rate": "bpm", "weight": "kg"}
LIMITS = {"blood_pressure": (50, 260), "glucose": (20, 700), "heart_rate": (25, 250), "weight": (10, 300)}


class MeasurementIn(BaseModel):
    kind: Literal["blood_pressure", "glucose", "heart_rate", "weight"]
    value: float
    value2: float | None = None
    context: Literal["fasting", "post_meal", "random", "resting", "after_activity"] | None = None
    measured_at: datetime | None = None
    note: str | None = Field(None, max_length=255)

    @model_validator(mode="after")
    def check(self):  # noqa: ANN201
        lo, hi = LIMITS[self.kind]
        if not (lo <= self.value <= hi):
            raise ValueError(f"That value looks unusual for {self.kind.replace('_', ' ')} — please check it")
        if self.kind == "blood_pressure":
            if self.value2 is None or not (30 <= self.value2 <= 160) or self.value2 >= self.value:
                raise ValueError("Enter both systolic (top) and diastolic (bottom) numbers")
        return self


@router.get("/measurements")
def list_measurements(kind: str | None = None, days: int = 30, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    q = select(HealthMeasurement).where(HealthMeasurement.user_id == user.id, HealthMeasurement.measured_at >= timeutil.now_utc() - timedelta(days=max(1, min(days, 730))))
    if kind:
        q = q.where(HealthMeasurement.kind == kind)
    rows = db.scalars(q.order_by(HealthMeasurement.measured_at.asc())).all()
    return {"items": [measurement_out(m) for m in rows]}


@router.get("/measurements/latest")
def latest(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    out = {}
    for kind in UNITS:
        m = db.scalar(select(HealthMeasurement).where(HealthMeasurement.user_id == user.id, HealthMeasurement.kind == kind).order_by(HealthMeasurement.measured_at.desc()).limit(1))
        out[kind] = measurement_out(m) if m else None
    return out


@router.post("/measurements")
def add_measurement(body: MeasurementIn, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    m = HealthMeasurement(user_id=user.id, kind=body.kind, value=body.value, value2=body.value2, unit=UNITS[body.kind], context=body.context,
                          measured_at=body.measured_at or timeutil.now_utc(), source="manual", note=body.note)
    db.add(m)
    db.flush()
    audit(db, "measurement.create", actor_id=user.id, resource_type="measurement", resource_id=m.id, meta={"kind": body.kind}, request=request)
    db.commit()
    return {"measurement": measurement_out(m)}


@router.delete("/measurements/{mid}")
def delete_measurement(mid: str, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    m = db.get(HealthMeasurement, mid)
    if not m or m.user_id != user.id:
        raise HTTPException(404, "Not found")
    db.delete(m)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ check-ins
class CheckinIn(BaseModel):
    mood: Literal["great", "good", "okay", "unwell"]
    energy: int | None = Field(None, ge=1, le=5)
    note: str | None = Field(None, max_length=500)


@router.post("/checkins")
def checkin(body: CheckinIn, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    day = timeutil.local_today(user.profile.timezone if user.profile else None)
    row = db.scalar(select(DailyCheckin).where(DailyCheckin.user_id == user.id, DailyCheckin.checkin_date == day))
    if not row:
        row = DailyCheckin(user_id=user.id, checkin_date=day, mood=body.mood)
        db.add(row)
    row.mood, row.energy, row.note = body.mood, body.energy, body.note
    db.commit()
    return {"checkin": {"date": day.isoformat(), "mood": row.mood, "energy": row.energy, "note": row.note}}


@router.get("/checkins/today")
def checkin_today(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    day = timeutil.local_today(user.profile.timezone if user.profile else None)
    row = db.scalar(select(DailyCheckin).where(DailyCheckin.user_id == user.id, DailyCheckin.checkin_date == day))
    return {"checkin": {"date": day.isoformat(), "mood": row.mood, "energy": row.energy, "note": row.note} if row else None}


# ------------------------------------------------------------------ timeline
CATEGORIES = ["report", "prescription", "document", "appointment", "measurement", "medicine", "checkin", "nutrition"]


@router.get("/timeline")
def timeline(category: str | None = None, start: date | None = None, end: date | None = None, q: str | None = None,
             user: User = Depends(require_patient), db: Session = Depends(get_db)):
    cats = set(category.split(",")) if category else set(CATEGORIES)
    tz = timeutil.tz_for(user.profile.timezone if user.profile else None)
    lo = datetime.combine(start or date(1970, 1, 1), datetime.min.time(), tzinfo=tz)
    hi = datetime.combine(end or date(2100, 1, 1), datetime.max.time(), tzinfo=tz)
    ev: list[dict] = []
    uid = user.id
    if "report" in cats:
        for r in db.scalars(select(MedicalReport).where(MedicalReport.user_id == uid)):
            when = datetime.combine(r.report_date, datetime.min.time(), tzinfo=tz) if r.report_date else r.created_at
            ab = sum(1 for p in r.parameters if p.status in ("high", "low"))
            ev.append({"id": r.id, "category": "report", "title": r.title, "subtitle": f"{len(r.parameters)} results · {ab} outside range" + (" · sample" if r.is_sample else ""),
                       "at": when, "link": f"/app/reports/{r.id}", "severity": "warning" if ab else "ok"})
    if "prescription" in cats:
        for p in db.scalars(select(Prescription).where(Prescription.user_id == uid)):
            when = datetime.combine(p.prescribed_date, datetime.min.time(), tzinfo=tz) if p.prescribed_date else p.created_at
            ev.append({"id": p.id, "category": "prescription", "title": f"Prescription — {p.doctor_name or 'Doctor'}", "subtitle": f"{len(p.medicines)} medicine(s)", "at": when,
                       "link": "/app/medicines", "severity": "ok"})
    if "document" in cats:
        for d in db.scalars(select(MedicalDocument).where(MedicalDocument.user_id == uid)):
            ev.append({"id": d.id, "category": "document", "title": d.filename, "subtitle": f"{(d.detected_type or d.declared_type or 'document').replace('_', ' ')} · {d.status.replace('_', ' ')}",
                       "at": d.created_at, "link": f"/app/documents/{d.id}", "severity": "warning" if d.status == "needs_review" else "ok"})
    if "appointment" in cats:
        for a in db.scalars(select(Appointment).where(Appointment.user_id == uid)):
            ev.append({"id": a.id, "category": "appointment", "title": f"{a.doctor_name}" + (f" · {a.specialization}" if a.specialization else ""), "subtitle": f"{a.status} · {a.clinic or ''}".strip(" ·"),
                       "at": a.scheduled_at, "link": "/app/appointments", "severity": "ok"})
    if "measurement" in cats:
        for m in db.scalars(select(HealthMeasurement).where(HealthMeasurement.user_id == uid)):
            v = f"{m.value:g}/{m.value2:g}" if m.value2 else f"{m.value:g}"
            ev.append({"id": m.id, "category": "measurement", "title": f"{m.kind.replace('_', ' ').title()}: {v} {m.unit}", "subtitle": ("Sample data · " if m.is_sample else "") + (m.context or m.source),
                       "at": m.measured_at, "link": "/app", "severity": "ok"})
    if "medicine" in cats:
        rows = db.execute(select(func.date(MedicineLog.scheduled_for), MedicineLog.status, func.count()).where(MedicineLog.user_id == uid, MedicineLog.status.in_(["taken", "skipped", "missed"]))
                          .group_by(func.date(MedicineLog.scheduled_for), MedicineLog.status)).all()
        days: dict = {}
        for d, s, n in rows:
            days.setdefault(d, {})[s] = n
        for d, c in days.items():
            dd = d if isinstance(d, date) else date.fromisoformat(str(d))
            ev.append({"id": f"med-{dd}", "category": "medicine", "title": f"Medicines: {c.get('taken', 0)} taken" + (f", {c.get('missed', 0)} missed" if c.get("missed") else "") + (f", {c.get('skipped', 0)} skipped" if c.get("skipped") else ""),
                       "subtitle": "Daily medicine log", "at": datetime.combine(dd, datetime.max.time().replace(microsecond=0), tzinfo=tz), "link": "/app/medicines", "severity": "warning" if c.get("missed") else "ok"})
    if "checkin" in cats:
        for c in db.scalars(select(DailyCheckin).where(DailyCheckin.user_id == uid)):
            ev.append({"id": c.id, "category": "checkin", "title": f"Daily check-in: feeling {c.mood}", "subtitle": c.note or "", "at": datetime.combine(c.checkin_date, datetime.min.time().replace(hour=9), tzinfo=tz),
                       "link": "/app", "severity": "warning" if c.mood == "unwell" else "ok"})
    if "nutrition" in cats:
        for p in db.scalars(select(NutritionPlan).where(NutritionPlan.user_id == uid)):
            ev.append({"id": p.id, "category": "nutrition", "title": "Meal plan created", "subtitle": f"Week of {p.week_start}" + (" · active" if p.is_active else ""), "at": p.created_at,
                       "link": "/app/nutrition/planner", "severity": "ok"})
    ev = [e for e in ev if lo <= timeutil.ensure_aware(e["at"]) <= hi]
    if q:
        ev = [e for e in ev if q.lower() in (e["title"] + " " + e["subtitle"]).lower()]
    ev.sort(key=lambda e: timeutil.ensure_aware(e["at"]), reverse=True)
    for e in ev:
        e["at"] = iso(e["at"])
    return {"items": ev[:500], "categories": CATEGORIES}
