from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.serializers import notification_out
from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models import Notification, PushSubscription, ReminderSettings, User
from app.services import timeutil
from app.services.notify import create_notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(unread: bool = False, limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Notification).where(Notification.user_id == user.id)
    if unread:
        q = q.where(Notification.read_at.is_(None))
    rows = db.scalars(q.order_by(Notification.created_at.desc()).limit(max(1, min(limit, 200)))).all()
    unread_count = db.query(Notification).filter(Notification.user_id == user.id, Notification.read_at.is_(None)).count()
    return {"items": [notification_out(n) for n in rows], "unread": unread_count}


@router.post("/{nid}/read")
def mark_read(nid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Not found")
    n.read_at = n.read_at or timeutil.now_utc()
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)).values(read_at=timeutil.now_utc()))
    db.commit()
    return {"ok": True}


@router.get("/push/config")
def push_config():
    s = get_settings()
    return {"enabled": s.push_enabled, "public_key": s.vapid_public_key,
            "note": None if s.push_enabled else "Background push is not configured on this server (VAPID keys missing). Reminders still appear in the app and are spoken aloud while the app is open."}


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)
    keys: dict[str, str]


@router.post("/push/subscribe")
def subscribe(body: SubscriptionIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not get_settings().push_enabled:
        raise HTTPException(400, "Push notifications are not configured on this server")
    if not body.endpoint.startswith("https://"):
        raise HTTPException(422, "Invalid push endpoint")
    sub = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint))
    if not sub:
        sub = PushSubscription(user_id=user.id, endpoint=body.endpoint, p256dh=body.keys.get("p256dh", ""), auth=body.keys.get("auth", ""),
                               user_agent=(request.headers.get("user-agent") or "")[:255])
        db.add(sub)
    else:
        sub.user_id = user.id
    db.commit()
    return {"ok": True}


@router.delete("/push/subscribe")
def unsubscribe(endpoint: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id))
    if sub:
        db.delete(sub)
        db.commit()
    return {"ok": True}


@router.post("/test")
def test_notification(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = create_notification(db, user.id, "system", "Test reminder", "This is how your medicine reminders will look.", data={"url": "/app/notifications"})
    db.commit()
    return {"notification": notification_out(n) if n else None, "push_status": n.push_status if n else None}


class ReminderSettingsIn(BaseModel):
    voice_enabled: bool = True
    voice_language: str = Field("hi-IN", pattern=r"^(hi-IN|en-IN|en-US|en-GB)$")
    voice_name: str | None = Field(None, max_length=120)
    volume: float = Field(1.0, ge=0, le=1)
    rate: float = Field(0.9, ge=0.5, le=1.5)
    repeat_count: int = Field(2, ge=1, le=5)
    repeat_interval_minutes: int = Field(10, ge=5, le=60)
    snooze_minutes: int = Field(15, ge=5, le=60)
    push_enabled: bool = True
    in_app_enabled: bool = True
    refill_alerts: bool = True
    appointment_alerts: bool = True
    quiet_hours_start: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    quiet_hours_end: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


def _settings_out(r: ReminderSettings) -> dict:
    return {k: getattr(r, k) for k in ReminderSettingsIn.model_fields}


@router.get("/reminder-settings")
def get_reminder_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.scalar(select(ReminderSettings).where(ReminderSettings.user_id == user.id))
    if not r:
        r = ReminderSettings(user_id=user.id)
        db.add(r)
        db.commit()
    return {"settings": _settings_out(r), "push": push_config()}


@router.put("/reminder-settings")
def put_reminder_settings(body: ReminderSettingsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.scalar(select(ReminderSettings).where(ReminderSettings.user_id == user.id))
    if not r:
        r = ReminderSettings(user_id=user.id)
        db.add(r)
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    db.commit()
    return {"settings": _settings_out(r)}
