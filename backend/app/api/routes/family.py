"""Family & caretaker connections (patient side), invitations, and the caregiver dashboard."""
from __future__ import annotations

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import accept_invite
from app.api.serializers import appointment_out, connection_out, iso, measurement_out, report_out
from app.core.config import get_settings
from app.core.security import client_ip, get_current_user, hash_token, new_invite_token, require_caregiver, require_patient
from app.db.session import get_db
from app.models import Appointment, CaregiverConnection, HealthMeasurement, MedicalReport, NutritionPlan, User
from app.services import scheduling, timeutil
from app.services.audit import audit
from app.services.consent import DEFAULT_PERMISSIONS, PERMISSIONS, connection_allows, latest_consent, record_consent
from app.services.notify import create_notification

router = APIRouter(tags=["family"])
MAX_CONTACTS = 3
Relationship = Literal["son", "daughter", "spouse", "family", "housemate", "caretaker"]


class InviteIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    relationship: Relationship
    phone: str | None = Field(None, max_length=30)
    permissions: dict[str, bool] = Field(default_factory=lambda: dict(DEFAULT_PERMISSIONS))
    escalation_minutes: int = Field(30, ge=10, le=240)
    is_emergency_contact: bool = False
    consent: bool


class PermissionsIn(BaseModel):
    permissions: dict[str, bool]
    escalation_minutes: int | None = Field(None, ge=10, le=240)
    is_emergency_contact: bool | None = None


@router.get("/family")
def list_family(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    conns = db.scalars(select(CaregiverConnection).where(CaregiverConnection.patient_user_id == user.id, CaregiverConnection.status.in_(["pending", "active"]))
                       .order_by(CaregiverConnection.created_at)).all()
    out = []
    for c in conns:
        cg = db.get(User, c.caregiver_user_id) if c.caregiver_user_id else None
        d = connection_out(c, cg)
        rec = latest_consent(db, user.id, "caregiver_share", c.id)
        d["consent"] = {"granted": bool(rec and rec.granted), "at": iso(rec.created_at) if rec else None}
        out.append(d)
    return {"items": out, "max": MAX_CONTACTS, "permission_labels": PERMISSIONS}


@router.post("/family/invite")
def invite(body: InviteIn, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    if not body.consent:
        raise HTTPException(400, "Please confirm you agree to share the selected information")
    active = db.query(CaregiverConnection).filter(CaregiverConnection.patient_user_id == user.id, CaregiverConnection.status.in_(["pending", "active"])).count()
    if active >= MAX_CONTACTS:
        raise HTTPException(400, f"You can connect up to {MAX_CONTACTS} trusted contacts")
    if body.email.lower() == user.email.lower():
        raise HTTPException(400, "Use a different email address than your own")
    token, token_hash = new_invite_token()
    perms = {k: bool(body.permissions.get(k, False)) for k in PERMISSIONS}
    conn = CaregiverConnection(patient_user_id=user.id, invite_email=body.email.lower(), name=body.name, relationship_type=body.relationship, phone=body.phone,
                               permissions=perms, escalation_minutes=body.escalation_minutes, is_emergency_contact=body.is_emergency_contact,
                               invite_token_hash=token_hash, invite_expires_at=timeutil.now_utc() + timedelta(days=7))
    db.add(conn)
    db.flush()
    record_consent(db, user.id, "caregiver_share", True, target_id=conn.id, scope=perms, ip=client_ip(request))
    existing = db.scalar(select(User).where(User.email == body.email.lower(), User.role == "caregiver"))
    if existing:
        create_notification(db, existing.id, "caregiver", "New care invitation", f"{user.full_name} invited you to be their {body.relationship}.",
                            data={"url": f"/invite/{token}"}, push=False)
    audit(db, "family.invite", actor_id=user.id, resource_type="caregiver_connection", resource_id=conn.id, meta={"relationship": body.relationship, "permissions": perms}, request=request)
    db.commit()
    link = f"{get_settings().frontend_origin}/invite/{token}"
    return {"connection": connection_out(conn), "invite_link": link,
            "delivery": "Email delivery is not configured in this build — share this link with your family member (WhatsApp/SMS)."}


def _conn(db: Session, user: User, cid: str) -> CaregiverConnection:
    c = db.get(CaregiverConnection, cid)
    if not c or c.patient_user_id != user.id:
        raise HTTPException(404, "Connection not found")
    return c


@router.put("/family/{cid}/permissions")
def update_permissions(cid: str, body: PermissionsIn, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    c = _conn(db, user, cid)
    perms = {k: bool(body.permissions.get(k, False)) for k in PERMISSIONS}
    c.permissions = perms
    if body.escalation_minutes:
        c.escalation_minutes = body.escalation_minutes
    if body.is_emergency_contact is not None:
        c.is_emergency_contact = body.is_emergency_contact
    record_consent(db, user.id, "caregiver_share", any(perms.values()), target_id=c.id, scope=perms, ip=client_ip(request))
    audit(db, "family.permissions_update", actor_id=user.id, resource_type="caregiver_connection", resource_id=c.id, meta={"permissions": perms}, request=request)
    db.commit()
    return {"connection": connection_out(c, db.get(User, c.caregiver_user_id) if c.caregiver_user_id else None)}


@router.delete("/family/{cid}")
def revoke(cid: str, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    c = _conn(db, user, cid)
    c.status, c.invite_token_hash = "revoked", None
    record_consent(db, user.id, "caregiver_share", False, target_id=c.id, ip=client_ip(request))
    if c.caregiver_user_id:
        create_notification(db, c.caregiver_user_id, "caregiver", "Access removed", f"{user.full_name} has removed your access.", push=False)
    audit(db, "family.revoke", actor_id=user.id, resource_type="caregiver_connection", resource_id=c.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/family/{cid}/resend")
def resend(cid: str, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    c = _conn(db, user, cid)
    if c.status != "pending":
        raise HTTPException(400, "Only pending invitations can be re-sent")
    token, token_hash = new_invite_token()
    c.invite_token_hash, c.invite_expires_at = token_hash, timeutil.now_utc() + timedelta(days=7)
    db.commit()
    return {"invite_link": f"{get_settings().frontend_origin}/invite/{token}"}


# ------------------------------------------------------------------ invitations (public lookup + accept)
@router.get("/invitations/{token}")
def invitation_info(token: str, db: Session = Depends(get_db)):
    c = db.scalar(select(CaregiverConnection).where(CaregiverConnection.invite_token_hash == hash_token(token)))
    if not c or c.status != "pending":
        raise HTTPException(404, "Invitation not found or already used")
    patient = db.get(User, c.patient_user_id)
    return {"patient_first_name": patient.full_name.split()[0], "relationship": c.relationship_type, "invitee_name": c.name, "invite_email": c.invite_email,
            "permissions": [PERMISSIONS[k] for k, v in (c.permissions or {}).items() if v and k in PERMISSIONS],
            "expires_at": iso(c.invite_expires_at)}


@router.post("/invitations/{token}/accept")
def accept(token: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "caregiver":
        raise HTTPException(403, "Please sign in with a caregiver account to accept")
    c = accept_invite(db, user, token)
    patient = db.get(User, c.patient_user_id)
    create_notification(db, patient.id, "caregiver", "Family member connected", f"{user.full_name} accepted your invitation.", data={"url": "/app/family"}, push=False)
    audit(db, "family.accept", actor_id=user.id, patient_id=patient.id, resource_type="caregiver_connection", resource_id=c.id, request=request)
    db.commit()
    return {"ok": True, "patient": {"id": patient.id, "full_name": patient.full_name}}


# ------------------------------------------------------------------ caregiver dashboard
@router.get("/caregiver/patients")
def my_patients(user: User = Depends(require_caregiver), db: Session = Depends(get_db)):
    conns = db.scalars(select(CaregiverConnection).where(CaregiverConnection.caregiver_user_id == user.id, CaregiverConnection.status == "active")).all()
    out = []
    for c in conns:
        p = db.get(User, c.patient_user_id)
        item = {"connection_id": c.id, "patient_id": p.id, "full_name": p.full_name, "relationship": c.relationship_type,
                "permissions": {k: connection_allows(db, c, k) for k in PERMISSIONS}}
        if connection_allows(db, c, "adherence_summary"):
            item["adherence_7d"] = scheduling.adherence(db, p.id, 7)["percent"]
        if connection_allows(db, c, "view_medicines"):
            doses = scheduling.doses_for_day(db, p.id)
            item["today"] = {"taken": sum(1 for d in doses if d["status"] == "taken"), "total": len(doses),
                             "attention": sum(1 for d in doses if d["status"] in ("overdue", "missed"))}
        out.append(item)
    return {"items": out}


@router.get("/caregiver/patients/{patient_id}/summary")
def patient_summary(patient_id: str, request: Request, user: User = Depends(require_caregiver), db: Session = Depends(get_db)):
    c = db.scalar(select(CaregiverConnection).where(CaregiverConnection.caregiver_user_id == user.id, CaregiverConnection.patient_user_id == patient_id,
                                                    CaregiverConnection.status == "active"))
    if not c:
        raise HTTPException(403, "You don't have access to this person's information")
    p = db.get(User, patient_id)
    allowed = {k: connection_allows(db, c, k) for k in PERMISSIONS}
    out: dict = {"patient": {"id": p.id, "full_name": p.full_name}, "relationship": c.relationship_type, "permissions": allowed}
    if allowed["view_medicines"]:
        out["doses_today"] = [{k: d[k] for k in ("name", "strength", "dosage", "slot", "effective_time", "status", "meal_relation")} for d in scheduling.doses_for_day(db, p.id)]
    if allowed["adherence_summary"]:
        out["adherence"] = scheduling.adherence(db, p.id, 7)
    if allowed["view_appointments"]:
        rows = db.scalars(select(Appointment).where(Appointment.user_id == p.id, Appointment.status == "upcoming", Appointment.scheduled_at >= timeutil.now_utc())
                          .order_by(Appointment.scheduled_at).limit(5)).all()
        out["appointments"] = [{k: v for k, v in appointment_out(a).items() if k not in ("notes", "consultation_summary")} for a in rows]
    if allowed["view_reports"]:
        rows = db.scalars(select(MedicalReport).where(MedicalReport.user_id == p.id).order_by(MedicalReport.report_date.desc().nulls_last()).limit(5)).all()
        out["reports"] = [report_out(r) for r in rows]
    if allowed["view_measurements"]:
        rows = db.scalars(select(HealthMeasurement).where(HealthMeasurement.user_id == p.id).order_by(HealthMeasurement.measured_at.desc()).limit(10)).all()
        out["measurements"] = [measurement_out(m) for m in rows]
    if allowed["view_nutrition"]:
        plan = db.scalar(select(NutritionPlan).where(NutritionPlan.user_id == p.id, NutritionPlan.is_active.is_(True)))
        out["nutrition_rules"] = plan.constraints.get("hard", {}) if plan else {}
    if c.is_emergency_contact:
        prof = p.profile
        out["emergency"] = {"patient_phone": prof.phone if prof else None, "emergency_contact_name": prof.emergency_contact_name if prof else None,
                            "emergency_contact_phone": prof.emergency_contact_phone if prof else None}
    audit(db, "caregiver.view_summary", actor_id=user.id, patient_id=p.id, resource_type="patient", resource_id=p.id, meta={"permissions": [k for k, v in allowed.items() if v]}, request=request, commit=True)
    return out
