"""Consent ledger + caregiver permission checks.

Rule: no medical information reaches a caregiver unless (1) the connection is active,
(2) the specific permission flag is on, and (3) the latest caregiver_share consent
record for that connection is `granted=True`.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CaregiverConnection, ConsentRecord

PERMISSIONS = {
    "view_medicines": "See medicine schedule",
    "missed_medicine_alerts": "Alert me when a medicine is missed",
    "adherence_summary": "See medicine adherence summaries",
    "view_appointments": "See upcoming appointments",
    "appointment_alerts": "Alert me before appointments",
    "view_reports": "See medical report summaries",
    "view_measurements": "See health measurements",
    "daily_summary": "Receive a daily health summary",
    "view_nutrition": "See meal plan",
}
DEFAULT_PERMISSIONS = {
    "view_medicines": True,
    "missed_medicine_alerts": True,
    "adherence_summary": True,
    "view_appointments": True,
    "appointment_alerts": True,
    "view_reports": False,
    "view_measurements": False,
    "daily_summary": True,
    "view_nutrition": False,
}


def record_consent(db: Session, user_id: str, consent_type: str, granted: bool, *, target_id: str | None = None,
                   scope: dict | None = None, ip: str | None = None) -> ConsentRecord:
    rec = ConsentRecord(user_id=user_id, consent_type=consent_type, granted=granted, target_id=target_id, scope=scope or {}, ip_address=ip)
    db.add(rec)
    db.flush()
    return rec


def latest_consent(db: Session, user_id: str, consent_type: str, target_id: str | None = None) -> ConsentRecord | None:
    q = select(ConsentRecord).where(ConsentRecord.user_id == user_id, ConsentRecord.consent_type == consent_type)
    if target_id is not None:
        q = q.where(ConsentRecord.target_id == target_id)
    return db.scalar(q.order_by(ConsentRecord.created_at.desc()).limit(1))


def has_consent(db: Session, user_id: str, consent_type: str, target_id: str | None = None) -> bool:
    rec = latest_consent(db, user_id, consent_type, target_id)
    return bool(rec and rec.granted)


def connection_allows(db: Session, conn: CaregiverConnection, permission: str) -> bool:
    if conn.status != "active" or not conn.caregiver_user_id:
        return False
    if not (conn.permissions or {}).get(permission):
        return False
    return has_consent(db, conn.patient_user_id, "caregiver_share", conn.id)


def caregivers_with_permission(db: Session, patient_id: str, permission: str) -> list[CaregiverConnection]:
    conns = db.scalars(
        select(CaregiverConnection).where(CaregiverConnection.patient_user_id == patient_id, CaregiverConnection.status == "active")
    ).all()
    return [c for c in conns if connection_allows(db, c, permission)]
