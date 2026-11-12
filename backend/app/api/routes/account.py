"""Data export, account deletion, audit log, dashboard aggregate and system status."""
from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import appointment_out, connection_out, document_out, iso, measurement_out, medicine_out, notification_out, report_out, user_out
from app.core.config import get_settings
from app.core.security import COOKIE_NAME, get_current_user, require_patient, verify_password
from app.db.session import get_db
from app.models import (
    AgentMemory,
    Appointment,
    AuditLog,
    CaregiverConnection,
    ChatMessage,
    ConsentRecord,
    DailyCheckin,
    HealthMeasurement,
    MealSchedule,
    MedicalDocument,
    MedicalReport,
    MedicineLog,
    Notification,
    PrescriptionMedicine,
    User,
)
from app.services import scheduling, timeutil
from app.services.audit import audit
from app.services.ocr import _tesseract_available
from app.services.storage import delete_file

router = APIRouter(tags=["account"])


@router.get("/account/export")
def export(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = user.id

    def rows(model, order=None):  # noqa: ANN001, ANN202
        q = select(model).where(model.user_id == uid)
        return db.scalars(q).all()

    data = {
        "exported_at": iso(timeutil.now_utc()), "format": "healthmate-export-v1",
        "user": user_out(user, user.profile),
        "medicines": [medicine_out(m) for m in rows(PrescriptionMedicine)],
        "medicine_logs": [{"medicine_id": lg.medicine_id, "scheduled_for": iso(lg.scheduled_for), "status": lg.status, "acted_at": iso(lg.acted_at)} for lg in rows(MedicineLog)],
        "reports": [report_out(r, with_params=True) for r in rows(MedicalReport)],
        "documents": [{**document_out(d), "extraction": d.extraction} for d in rows(MedicalDocument)],
        "appointments": [appointment_out(a) for a in rows(Appointment)],
        "measurements": [measurement_out(m) for m in rows(HealthMeasurement)],
        "meal_schedule": [{"meal": m.meal, "time": m.time_of_day} for m in rows(MealSchedule)],
        "checkins": [{"date": iso(c.checkin_date), "mood": c.mood, "note": c.note} for c in rows(DailyCheckin)],
        "caregivers": [connection_out(c) for c in db.scalars(select(CaregiverConnection).where(CaregiverConnection.patient_user_id == uid))],
        "consents": [{"type": c.consent_type, "granted": c.granted, "target_id": c.target_id, "at": iso(c.created_at)} for c in rows(ConsentRecord)],
        "assistant_memory": [{"content": m.content, "at": iso(m.created_at)} for m in rows(AgentMemory)],
        "chat_messages": [{"session": m.session_id, "role": m.role, "content": m.content, "at": iso(m.created_at)} for m in rows(ChatMessage)],
        "notifications": [notification_out(n) for n in rows(Notification)],
    }
    audit(db, "account.export", actor_id=uid, request=request, commit=True)
    import json

    return Response(json.dumps(data, ensure_ascii=False, indent=2, default=str), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="healthmate-export.json"', "Cache-Control": "no-store"})


class DeleteIn(BaseModel):
    password: str
    confirm: str


@router.post("/account/delete")
def delete_account(body: DeleteIn, request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.confirm != "DELETE":
        raise HTTPException(400, "Type DELETE to confirm")
    if not user.is_demo and not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Password is incorrect")
    uid = user.id
    audit(db, "account.delete", actor_id=uid, request=request)
    for d in db.scalars(select(MedicalDocument).where(MedicalDocument.user_id == uid)):
        delete_file(d.storage_key)
    folder = get_settings().data_dir / "documents" / uid
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
    db.query(CaregiverConnection).filter((CaregiverConnection.patient_user_id == uid)).delete()
    db.query(CaregiverConnection).filter(CaregiverConnection.caregiver_user_id == uid).update({"caregiver_user_id": None, "status": "revoked"})
    db.delete(user)  # cascades through ON DELETE CASCADE foreign keys
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/account/audit")
def audit_log(limit: int = 100, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).where((AuditLog.patient_user_id == user.id) | (AuditLog.actor_user_id == user.id))
                      .order_by(AuditLog.created_at.desc()).limit(max(1, min(limit, 500)))).all()
    actors = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({r.actor_user_id for r in rows if r.actor_user_id})))}
    return {"items": [{"id": r.id, "action": r.action, "actor": actors.get(r.actor_user_id, "System") if r.actor_user_id != user.id else "You",
                       "resource_type": r.resource_type, "meta": r.meta, "at": iso(r.created_at)} for r in rows]}


@router.get("/dashboard")
def dashboard(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    p = user.profile
    tz = p.timezone if p else None
    now = timeutil.local_now(tz)
    doses = scheduling.doses_for_day(db, user.id)
    nxt = next((d for d in doses if d["status"] in ("due", "upcoming")), None)
    appt = db.scalar(select(Appointment).where(Appointment.user_id == user.id, Appointment.status == "upcoming", Appointment.scheduled_at >= timeutil.now_utc())
                     .order_by(Appointment.scheduled_at).limit(1))
    reps = db.scalars(select(MedicalReport).where(MedicalReport.user_id == user.id).order_by(MedicalReport.report_date.desc().nulls_last()).limit(3)).all()
    meas = {}
    for kind in ("blood_pressure", "glucose", "heart_rate", "weight"):
        series = db.scalars(select(HealthMeasurement).where(HealthMeasurement.user_id == user.id, HealthMeasurement.kind == kind)
                            .order_by(HealthMeasurement.measured_at.desc()).limit(14)).all()
        meas[kind] = [measurement_out(m) for m in reversed(series)]
    conns = db.scalars(select(CaregiverConnection).where(CaregiverConnection.patient_user_id == user.id, CaregiverConnection.status.in_(["active", "pending"]))).all()
    pending = db.scalars(select(MedicalDocument).where(MedicalDocument.user_id == user.id, MedicalDocument.status.in_(["needs_review", "processing", "uploaded"]))
                         .order_by(MedicalDocument.created_at.desc())).all()
    unread = db.query(Notification).filter(Notification.user_id == user.id, Notification.read_at.is_(None)).count()
    from app.api.routes.medicines import meals_today
    from app.api.routes.nutrition import overview as nutrition_overview

    try:
        nut = nutrition_overview(user, db)
        today_meals = nut["today"]["meals"] if nut.get("today") else {}
    except Exception:  # noqa: BLE001
        today_meals = {}
    h = now.hour
    return {
        "greeting": "morning" if h < 12 else "afternoon" if h < 17 else "evening",
        "now": now.isoformat(), "user": user_out(user, p),
        "doses": doses, "next_dose": nxt,
        "dose_summary": {"taken": sum(1 for d in doses if d["status"] == "taken"), "total": len(doses), "attention": sum(1 for d in doses if d["status"] in ("overdue", "missed"))},
        "adherence": scheduling.adherence(db, user.id, 7),
        "meals": meals_today(user, db)["items"], "meal_plan_today": {m: [{"id": f["id"], "name": f["name"], "calories": f["calories"]} for f in fs] for m, fs in today_meals.items()},
        "next_appointment": appointment_out(appt) if appt else None,
        "recent_reports": [report_out(r) for r in reps],
        "measurements": meas,
        "family": [{"name": c.name, "relationship": c.relationship_type, "status": c.status} for c in conns],
        "pending_documents": [document_out(d) for d in pending[:5]],
        "unread_notifications": unread,
        "medicine_count": db.query(PrescriptionMedicine).filter(PrescriptionMedicine.user_id == user.id, PrescriptionMedicine.is_active.is_(True)).count(),
    }


@router.get("/system/status")
def system_status():
    s = get_settings()
    from app.services.llm import get_llm

    llm = get_llm()
    return {"llm": {"mode": "live" if llm else "demo", "provider": llm.name if llm else None, "model": llm.model if llm else None},
            "ocr": {"available": _tesseract_available(), "languages": s.ocr_languages}, "push": {"enabled": s.push_enabled},
            "reminder_engine": {"enabled": s.reminder_engine_enabled, "tick_seconds": s.reminder_tick_seconds},
            "email": {"enabled": False, "note": "Invitation links are shown in-app; no email provider configured."},
            "environment": s.environment}
