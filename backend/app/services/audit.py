"""Audit logging. Stores identifiers and action names only — never medical content."""
from __future__ import annotations

import logging

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.security import client_ip
from app.models import AuditLog

log = logging.getLogger("healthmate.audit")

_FORBIDDEN_META_KEYS = {"text", "ocr_text", "content", "notes", "value", "message", "extraction"}


def audit(
    db: Session,
    action: str,
    *,
    actor_id: str | None,
    patient_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    meta: dict | None = None,
    request: Request | None = None,
    commit: bool = False,
) -> None:
    safe_meta = {k: v for k, v in (meta or {}).items() if k not in _FORBIDDEN_META_KEYS}
    db.add(
        AuditLog(
            actor_user_id=actor_id,
            patient_user_id=patient_id or actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            meta=safe_meta,
            ip_address=client_ip(request) if request else None,
        )
    )
    log.info("audit action=%s actor=%s resource=%s:%s", action, actor_id, resource_type, resource_id)
    if commit:
        db.commit()
