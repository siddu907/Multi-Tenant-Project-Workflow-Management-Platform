from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.organization_repository import list_ids as list_organization_ids
from app.services.dashboard_service import (
    get_my_tasks_dashboard,
    get_organization_dashboard,
    get_project_manager_dashboard,
)

router = APIRouter()


@router.get("/dashboard/organization")
def organization_dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = user.role.name.lower() if user.role else ""
    if role == "super_admin":
        org_ids = list_organization_ids(db)
    else:
        org_ids = [
            membership.organization_id
            for membership in user.organization_memberships
            if membership.is_active and membership.role.lower() in {"org_admin", "admin"}
        ]
        if not org_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin dashboard access required")
    return get_organization_dashboard(db, org_ids)


@router.get("/dashboard/project-manager")
def project_manager_dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = user.role.name.lower() if user.role else ""
    if role == "super_admin":
        org_ids = list_organization_ids(db)
    else:
        org_ids = [
            membership.organization_id
            for membership in user.organization_memberships
            if membership.is_active and membership.role.lower() in {"org_admin", "project_manager", "admin"}
        ]
        if not org_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project manager dashboard access required")
    return get_project_manager_dashboard(db, org_ids)


@router.get("/dashboard/my-tasks")
def my_tasks_dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    active_org_ids = {
        membership.organization_id
        for membership in user.organization_memberships
        if membership.is_active
    }
    active_project_ids = [
        membership.project_id
        for membership in user.project_memberships
        if membership.is_active and membership.project.organization_id in active_org_ids
    ]
    return get_my_tasks_dashboard(db, user.id, active_project_ids)
