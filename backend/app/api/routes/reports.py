from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import report_out
from app.core.security import require_patient
from app.db.session import get_db
from app.models import MedicalReport, ReportParameter, User
from app.services import reports
from app.services.audit import audit
from app.services.medical_knowledge import KNOWLEDGE

router = APIRouter(prefix="/reports", tags=["reports"])

KEY_TRENDS = ["hba1c", "fasting_glucose", "ldl", "total_cholesterol", "hdl", "triglycerides", "creatinine", "hemoglobin", "tsh", "vitamin_d"]


@router.get("")
def list_reports(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rows = db.scalars(select(MedicalReport).where(MedicalReport.user_id == user.id).order_by(MedicalReport.report_date.desc().nulls_last(), MedicalReport.created_at.desc())).all()
    return {"items": [report_out(r) for r in rows]}


@router.get("/trends")
def trends(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    present = set(db.scalars(select(ReportParameter.canonical_name).where(ReportParameter.user_id == user.id)).all())
    out = []
    for c in [k for k in KEY_TRENDS if k in present]:
        hist = reports.parameter_history(db, user.id, c)
        if hist:
            out.append({"canonical": c, "label": KNOWLEDGE.get(c, {}).get("label", c), "label_hi": KNOWLEDGE.get(c, {}).get("label_hi"), "history": hist})
    return {"items": out}


@router.get("/parameters/{canonical}/history")
def history(canonical: str, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return {"canonical": canonical, "label": KNOWLEDGE.get(canonical, {}).get("label", canonical), "history": reports.parameter_history(db, user.id, canonical)}


@router.get("/{report_id}")
def get_report(report_id: str, request: Request, lang: str = "en", user: User = Depends(require_patient), db: Session = Depends(get_db)):
    r = db.get(MedicalReport, report_id)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Report not found")
    out = report_out(r, with_params=True)
    out["explanations"] = {p.id: {"en": reports.explain_parameter(p, "en"), "hi": reports.explain_parameter(p, "hi")} for p in r.parameters}
    out["comparison"] = reports.compare_with_previous(db, r)
    audit(db, "report.view", actor_id=user.id, resource_type="report", resource_id=r.id, request=request, commit=True)
    return {"report": out}


@router.delete("/{report_id}")
def delete_report(report_id: str, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    r = db.get(MedicalReport, report_id)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Report not found")
    db.delete(r)
    audit(db, "report.delete", actor_id=user.id, resource_type="report", resource_id=report_id, request=request)
    db.commit()
    return {"ok": True}
