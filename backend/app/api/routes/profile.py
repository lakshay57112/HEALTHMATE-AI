from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import iso, user_out
from app.core.security import client_ip, get_current_user, require_patient
from app.db.session import get_db
from app.models import ConsentRecord, MealSchedule, PatientProfile, User
from app.services import scheduling
from app.services.audit import audit
from app.services.consent import record_consent
from app.services.nutrition import generate_plan

router = APIRouter(tags=["profile"])

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class ProfileIn(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=120)
    language: Literal["en", "hi"] | None = None
    date_of_birth: date | None = None
    gender: Literal["male", "female", "other", "prefer_not_to_say"] | None = None
    phone: str | None = Field(None, max_length=30)
    blood_group: str | None = Field(None, max_length=5)
    height_cm: float | None = Field(None, gt=50, lt=250)
    weight_kg: float | None = Field(None, gt=10, lt=300)
    timezone: str | None = None
    conditions: list[str] | None = None
    allergies: list[str] | None = None
    food_preference: Literal["vegetarian", "eggetarian", "non_vegetarian", "vegan"] | None = None
    activity_level: Literal["sedentary", "light", "moderate", "active"] | None = None
    budget_preference: Literal["low", "moderate", "high"] | None = None
    emergency_contact_name: str | None = Field(None, max_length=120)
    emergency_contact_phone: str | None = Field(None, max_length=30)
    large_text: bool | None = None

    @field_validator("date_of_birth")
    @classmethod
    def dob_past(cls, v: date | None) -> date | None:
        if v and (v > date.today() or v.year < 1900):
            raise ValueError("Please enter a valid date of birth")
        return v

    @field_validator("conditions", "allergies")
    @classmethod
    def clean_list(cls, v: list[str] | None) -> list[str] | None:
        return [x.strip()[:60] for x in v if x and x.strip()][:20] if v is not None else None


class MealTime(BaseModel):
    meal: Literal["breakfast", "lunch", "snack", "dinner"]
    time: str = Field(pattern=HHMM)
    enabled: bool = True


class OnboardingIn(ProfileIn):
    meals: list[MealTime] = []
    ai_processing_consent: bool


def apply_profile(db: Session, user: User, body: ProfileIn) -> PatientProfile:
    data = body.model_dump(exclude_unset=True)
    for k in ("full_name", "language"):
        if data.get(k) is not None:
            setattr(user, k, data.pop(k))
        data.pop(k, None)
    p = user.profile
    for k, v in data.items():
        if k in ("meals", "ai_processing_consent"):
            continue
        if hasattr(p, k):
            setattr(p, k, v)
    return p


def save_meals(db: Session, user_id: str, meals: list[MealTime]) -> None:
    existing = {m.meal: m for m in db.scalars(select(MealSchedule).where(MealSchedule.user_id == user_id))}
    for m in meals:
        row = existing.get(m.meal)
        if row:
            row.time_of_day, row.enabled = m.time, m.enabled
        else:
            db.add(MealSchedule(user_id=user_id, meal=m.meal, time_of_day=m.time, enabled=m.enabled))
    db.flush()
    scheduling.regenerate_all_for_user(db, user_id)


@router.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    return {"user": user_out(user, user.profile)}


@router.put("/profile")
def update_profile(body: ProfileIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.merge(user)
    if user.role == "patient":
        apply_profile(db, user, body)
        if body.conditions is not None or body.allergies is not None or body.food_preference is not None:
            generate_plan(db, user)
    else:
        if body.full_name:
            user.full_name = body.full_name
        if body.language:
            user.language = body.language
    audit(db, "profile.update", actor_id=user.id, resource_type="profile", meta={"fields": sorted(body.model_dump(exclude_unset=True).keys())}, request=request)
    db.commit()
    return {"user": user_out(user, user.profile)}


@router.post("/profile/onboarding")
def onboarding(body: OnboardingIn, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    user = db.merge(user)
    if not body.ai_processing_consent:
        raise HTTPException(400, "AI document processing needs your consent. You can still add information manually later.")
    p = apply_profile(db, user, body)
    if body.meals:
        save_meals(db, user.id, body.meals)
    record_consent(db, user.id, "ai_processing", True, scope={"documents": True, "assistant": True}, ip=client_ip(request))
    p.onboarding_complete = True
    generate_plan(db, user)
    audit(db, "profile.onboarding_complete", actor_id=user.id, request=request)
    db.commit()
    return {"user": user_out(user, p)}


@router.get("/consents")
def consents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id).order_by(ConsentRecord.created_at.desc())).all()
    return {"items": [{"id": r.id, "type": r.consent_type, "target_id": r.target_id, "granted": r.granted, "scope": r.scope, "created_at": iso(r.created_at)} for r in rows]}


class ConsentIn(BaseModel):
    consent_type: Literal["ai_processing"]
    granted: bool


@router.post("/consents")
def set_consent(body: ConsentIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rec = record_consent(db, user.id, body.consent_type, body.granted, ip=client_ip(request))
    audit(db, "consent.update", actor_id=user.id, resource_type="consent", resource_id=rec.id, meta={"type": body.consent_type, "granted": body.granted}, request=request)
    db.commit()
    return {"ok": True}
