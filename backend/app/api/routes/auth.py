from __future__ import annotations

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serializers import user_out
from app.core.config import get_settings
from app.core.security import COOKIE_NAME, client_ip, create_access_token, get_current_user, hash_password, hash_token, verify_password
from app.db.session import get_db
from app.models import CaregiverConnection, MealSchedule, PatientProfile, ReminderSettings, User
from app.services import timeutil
from app.services.audit import audit
from app.services.consent import record_consent
from app.services.scheduling import DEFAULT_MEAL_TIMES

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    role: Literal["patient", "caregiver"] = "patient"
    language: Literal["en", "hi"] = "en"
    accept_terms: bool
    invite_token: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def _set_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(COOKIE_NAME, token, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=settings.access_token_minutes * 60, path="/")


def init_patient(db: Session, user: User) -> PatientProfile:
    profile = PatientProfile(user_id=user.id, timezone=settings.default_timezone)
    db.add(profile)
    db.add(ReminderSettings(user_id=user.id, voice_language="hi-IN" if user.language == "hi" else "en-IN"))
    for meal, t in DEFAULT_MEAL_TIMES.items():
        db.add(MealSchedule(user_id=user.id, meal=meal, time_of_day=t))
    return profile


def accept_invite(db: Session, user: User, token: str) -> CaregiverConnection:
    conn = db.scalar(select(CaregiverConnection).where(CaregiverConnection.invite_token_hash == hash_token(token)))
    if not conn or conn.status != "pending":
        raise HTTPException(400, "This invitation is invalid or has already been used")
    if conn.invite_expires_at and timeutil.ensure_aware(conn.invite_expires_at) < timeutil.now_utc():
        raise HTTPException(400, "This invitation has expired. Ask for a new one.")
    if conn.patient_user_id == user.id:
        raise HTTPException(400, "You cannot accept your own invitation")
    conn.caregiver_user_id, conn.status, conn.accepted_at, conn.invite_token_hash = user.id, "active", timeutil.now_utc(), None
    return conn


@router.post("/register")
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if not body.accept_terms:
        raise HTTPException(400, "Please accept the terms and privacy policy to continue")
    if db.scalar(select(User).where(func.lower(User.email) == body.email.lower())):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), full_name=body.full_name.strip(), role=body.role, language=body.language)
    db.add(user)
    db.flush()
    profile = init_patient(db, user) if body.role == "patient" else None
    record_consent(db, user.id, "terms", True, ip=client_ip(request))
    if body.invite_token:
        accept_invite(db, user, body.invite_token)
    audit(db, "auth.register", actor_id=user.id, resource_type="user", resource_id=user.id, meta={"role": body.role}, request=request)
    db.commit()
    _set_cookie(response, create_access_token(user))
    return {"user": user_out(user, profile)}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        audit(db, "auth.login_failed", actor_id=None, meta={"email_domain": body.email.split("@")[-1]}, request=request, commit=True)
        raise HTTPException(401, "Email or password is incorrect")
    audit(db, "auth.login", actor_id=user.id, request=request, commit=True)
    _set_cookie(response, create_access_token(user))
    return {"user": user_out(user, user.profile)}


@router.post("/demo")
def demo_login(request: Request, response: Response, role: Literal["patient", "caregiver"] = "patient", db: Session = Depends(get_db)):
    """Signs into the seeded demo account (sample data, clearly labelled)."""
    email = "demo.patient@healthmate.app" if role == "patient" else "demo.caregiver@healthmate.app"
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        from app.seed import seed_demo

        seed_demo(db)
        db.commit()
        user = db.scalar(select(User).where(User.email == email))
    audit(db, "auth.demo_login", actor_id=user.id, request=request, commit=True)
    _set_cookie(response, create_access_token(user))
    return {"user": user_out(user, user.profile)}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": user_out(user, user.profile)}


@router.post("/token")
def api_token(user: User = Depends(get_current_user)):
    """Bearer token for API clients such as the MCP server (same lifetime as the session)."""
    return {"access_token": create_access_token(user), "token_type": "bearer", "expires_in": int(timedelta(minutes=settings.access_token_minutes).total_seconds())}
