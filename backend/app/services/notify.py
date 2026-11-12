"""In-app notifications + Web Push (VAPID).

Web push is real when VAPID keys are configured (see scripts/generate_vapid_keys.py) and the
browser has subscribed. Without keys, notifications are stored in-app and the push status is
recorded as 'disabled' — we never pretend a push was delivered.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Notification, PushSubscription, ReminderSettings

log = logging.getLogger(__name__)


def send_web_push(db: Session, user_id: str, payload: dict) -> str:
    settings = get_settings()
    if not settings.push_enabled:
        return "disabled"
    subs = db.scalars(select(PushSubscription).where(PushSubscription.user_id == user_id)).all()
    if not subs:
        return "no_subscription"
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:  # pragma: no cover
        return "disabled"
    status = "failed"
    for sub in subs:
        try:
            webpush(
                subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                data=json.dumps(payload),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
                timeout=10,
            )
            status = "sent"
        except WebPushException as exc:  # expired subscriptions are removed
            code = getattr(exc.response, "status_code", None)
            if code in (404, 410):
                db.delete(sub)
            log.warning("web push failed status=%s", code)
        except Exception as exc:  # noqa: BLE001
            log.warning("web push error: %s", type(exc).__name__)
    return status


def create_notification(db: Session, user_id: str, kind: str, title: str, body: str, *, severity: str = "info",
                        data: dict | None = None, dedupe_key: str | None = None, push: bool = True) -> Notification | None:
    if dedupe_key and db.scalar(select(Notification.id).where(Notification.dedupe_key == dedupe_key)):
        return None
    n = Notification(user_id=user_id, kind=kind, title=title, body=body, severity=severity, data=data or {}, dedupe_key=dedupe_key)
    try:
        with db.begin_nested():
            db.add(n)
            db.flush()
    except IntegrityError:
        return None
    prefs = db.scalar(select(ReminderSettings).where(ReminderSettings.user_id == user_id))
    if push and (prefs is None or prefs.push_enabled):
        n.push_status = send_web_push(db, user_id, {"title": title, "body": body, "kind": kind, "id": n.id, "url": (data or {}).get("url", "/app/notifications")})
    else:
        n.push_status = "none"
    return n
