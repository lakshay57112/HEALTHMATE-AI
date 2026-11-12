"""Plain-dict serializers shared by routers (keeps response shapes consistent)."""
from __future__ import annotations

from app.models import (
    Appointment,
    CaregiverConnection,
    HealthMeasurement,
    MedicalDocument,
    MedicalReport,
    Notification,
    PatientProfile,
    PrescriptionMedicine,
    User,
)
from app.services.consent import PERMISSIONS


def iso(v):  # noqa: ANN001
    return v.isoformat() if v else None


def user_out(u: User, p: PatientProfile | None = None) -> dict:
    d = {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "language": u.language, "is_demo": u.is_demo}
    if p is not None:
        d["profile"] = profile_out(p)
    return d


def profile_out(p: PatientProfile) -> dict:
    return {"date_of_birth": iso(p.date_of_birth), "gender": p.gender, "phone": p.phone, "blood_group": p.blood_group, "height_cm": p.height_cm,
            "weight_kg": p.weight_kg, "timezone": p.timezone, "conditions": p.conditions or [], "allergies": p.allergies or [],
            "food_preference": p.food_preference, "cuisine_preferences": p.cuisine_preferences or [], "activity_level": p.activity_level,
            "budget_preference": p.budget_preference, "doctor_diet_instructions": p.doctor_diet_instructions or [],
            "emergency_contact_name": p.emergency_contact_name, "emergency_contact_phone": p.emergency_contact_phone,
            "onboarding_complete": p.onboarding_complete, "large_text": p.large_text}


def medicine_out(m: PrescriptionMedicine) -> dict:
    return {"id": m.id, "name": m.name, "brand_name": m.brand_name, "generic_name": m.generic_name, "form": m.form, "strength": m.strength, "dosage": m.dosage,
            "frequency": m.frequency, "slots": m.slots or [], "meal_relation": m.meal_relation, "duration_days": m.duration_days, "start_date": iso(m.start_date),
            "end_date": iso(m.end_date), "instructions": m.instructions, "source": m.source, "verified": m.verified, "is_active": m.is_active,
            "as_needed": m.as_needed, "stock_count": m.stock_count, "refill_threshold": m.refill_threshold, "color": m.color, "prescription_id": m.prescription_id,
            "schedules": [{"id": s.id, "slot": s.slot, "time": s.time_of_day, "rule": s.rule, "meal_anchor": s.meal_anchor, "offset_minutes": s.offset_minutes}
                          for s in m.schedules if s.active]}


def appointment_out(a: Appointment) -> dict:
    return {"id": a.id, "doctor_name": a.doctor_name, "specialization": a.specialization, "clinic": a.clinic, "address": a.address, "phone": a.phone,
            "scheduled_at": iso(a.scheduled_at), "status": a.status, "notes": a.notes, "consultation_summary": a.consultation_summary,
            "document_id": a.document_id, "prescription_id": a.prescription_id, "reminder_minutes_before": a.reminder_minutes_before, "source": a.source}


def report_out(r: MedicalReport, with_params: bool = False) -> dict:
    d = {"id": r.id, "title": r.title, "report_date": iso(r.report_date), "lab_name": r.lab_name, "document_id": r.document_id, "is_sample": r.is_sample,
         "created_at": iso(r.created_at), "parameter_count": len(r.parameters),
         "abnormal_count": sum(1 for p in r.parameters if p.status in ("high", "low"))}
    if with_params:
        d["parameters"] = [{"id": p.id, "test_group": p.test_group, "name": p.name, "canonical_name": p.canonical_name, "value": p.value, "value_text": p.value_text,
                            "unit": p.unit, "ref_low": p.ref_low, "ref_high": p.ref_high, "ref_text": p.ref_text, "status": p.status} for p in r.parameters]
        d["summary"] = r.summary
    return d


def document_out(d: MedicalDocument, detail: bool = False) -> dict:
    out = {"id": d.id, "filename": d.filename, "mime_type": d.mime_type, "size_bytes": d.size_bytes, "declared_type": d.declared_type,
           "detected_type": d.detected_type, "status": d.status, "confidence": d.confidence, "flags": d.flags or [], "created_at": iso(d.created_at),
           "verified_at": iso(d.verified_at), "document_date": iso(d.document_date), "extractor": d.extractor, "steps": d.pipeline_steps or [], "error": d.error}
    if detail:
        out["extraction"] = d.extraction
        out["ocr_method"] = d.ocr_method
        out["ocr_text_preview"] = (d.ocr_text or "")[:4000]
    return out


def measurement_out(m: HealthMeasurement) -> dict:
    return {"id": m.id, "kind": m.kind, "value": m.value, "value2": m.value2, "unit": m.unit, "context": m.context, "measured_at": iso(m.measured_at),
            "source": m.source, "is_sample": m.is_sample, "note": m.note}


def notification_out(n: Notification) -> dict:
    return {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "severity": n.severity, "data": n.data or {}, "read": n.read_at is not None,
            "created_at": iso(n.created_at), "push_status": n.push_status}


def connection_out(c: CaregiverConnection, caregiver: User | None = None) -> dict:
    return {"id": c.id, "name": c.name, "invite_email": c.invite_email, "relationship": c.relationship_type, "phone": c.phone, "status": c.status,
            "permissions": {k: bool((c.permissions or {}).get(k)) for k in PERMISSIONS}, "escalation_minutes": c.escalation_minutes,
            "is_emergency_contact": c.is_emergency_contact, "accepted_at": iso(c.accepted_at), "created_at": iso(c.created_at),
            "caregiver": {"id": caregiver.id, "full_name": caregiver.full_name, "email": caregiver.email} if caregiver else None}
