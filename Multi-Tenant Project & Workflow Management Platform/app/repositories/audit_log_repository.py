from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog

def create(db: Session, **kwargs):
    log = AuditLog(**kwargs)
    db.add(log)
    db.flush()
    return log


def list_for_user(db: Session, user_id: int):
    return db.scalars(select(AuditLog).where(AuditLog.user_id == user_id).order_by(AuditLog.created_at.desc())).all()


def list_for_organization(db: Session, organization_id: int):
    return db.scalars(select(AuditLog).where(AuditLog.organization_id == organization_id).order_by(AuditLog.created_at.desc())).all()


def list_filtered(
    db: Session,
    *,
    organization_ids: list[int] | None,
    organization_id: int | None,
    action: str | None,
    entity_type: str | None,
    page: int,
    page_size: int,
):
    query = select(AuditLog)
    if organization_ids is not None:
        query = query.where(AuditLog.organization_id.in_(organization_ids))
    if organization_id is not None:
        query = query.where(AuditLog.organization_id == organization_id)
    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    entries = db.scalars(
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return entries, total
