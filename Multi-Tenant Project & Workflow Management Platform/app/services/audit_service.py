from contextvars import ContextVar
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repositories.audit_log_repository import list_filtered

current_request_ip: ContextVar[str | None] = ContextVar("current_request_ip", default=None)


def request_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def record(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: int | None,
    user_id: int | None = None,
    organization_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        organization_id=organization_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata or {},
        ip_address=ip_address or current_request_ip.get(),
    )
    db.add(log)
    return log


def list_audit_events(
    db: Session,
    *,
    organization_ids: list[int] | None,
    organization_id: int | None,
    action: str | None,
    entity_type: str | None,
    page: int,
    page_size: int,
):
    return list_filtered(
        db,
        organization_ids=organization_ids,
        organization_id=organization_id,
        action=action,
        entity_type=entity_type,
        page=page,
        page_size=page_size,
    )
