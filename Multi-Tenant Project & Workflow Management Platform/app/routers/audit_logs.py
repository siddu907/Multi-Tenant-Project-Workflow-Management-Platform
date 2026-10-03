from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import normalize_role_name
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.audit_service import list_audit_events

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("")
def list_audit_logs(
    organization_id: int | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = normalize_role_name(user.role.name if user.role else None)
    if role == "super_admin":
        organization_ids = None
    else:
        organization_ids = [
            membership.organization_id
            for membership in user.organization_memberships
            if membership.is_active and normalize_role_name(membership.role) == "org_admin"
        ]
        if role != "org_admin" or not organization_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Audit log access requires administrator permissions")

    if organization_id is not None:
        if role != "super_admin" and organization_id not in organization_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot view audit logs for this organization")
    entries, total = list_audit_events(
        db,
        organization_ids=organization_ids,
        organization_id=organization_id,
        action=action,
        entity_type=entity_type,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [
            {
                "id": entry.id,
                "user_id": entry.user_id,
                "organization_id": entry.organization_id,
                "action": entry.action,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "ip_address": entry.ip_address,
                "metadata": entry.metadata_json,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in entries
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }
