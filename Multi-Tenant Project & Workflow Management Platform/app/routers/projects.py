from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.permissions import normalize_role_name
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.audit_service import record, request_ip
from app.services.notification_service import create_and_push_notification
from app.schemas.project import ProjectCreate, ProjectMemberCreate, ProjectUpdate
from app.services.project_service import (
    InvalidProjectStatus,
    InvalidProjectStatusTransition,
    add_member as persist_project_member,
    create_project as persist_project,
    delete_project as delete_project_record,
    validate_project_status,
        validate_project_status_transition,
        update_project_fields,
        archive_project as archive_project_record,
)
from app.services.authorization_service import (
    ensure_organization_manager as ensure_org_manager_access,
    ensure_project_access,
)
from app.repositories import organization_repository, project_repository, user_repository
from app.services.project_service import remove_member as remove_project_member_record

router = APIRouter(prefix="/projects")


def project_payload(project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "organization_id": project.organization_id,
        "owner_id": project.owner_id,
        "status": project.status,
        "start_date": project.start_date,
        "due_date": project.due_date,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


@router.post("")
def create_project(request: ProjectCreate, http_request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    request = request.model_dump()
    organization_id = request["organization_id"]
    if organization_repository.get_by_id(db, organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ensure_org_manager_access(user, organization_id)
    name = str(request.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project name is required")
    try:
        project_status = validate_project_status(str(request.get("status") or "planning"))
    except InvalidProjectStatus as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    start_date = request.get("start_date")
    due_date = request.get("due_date")
    start_date = request.get("start_date")
    due_date = request.get("due_date")
    project = persist_project(
        db,
        name=name,
        description=request.get("description"),
        organization_id=organization_id,
        owner_id=user.id,
        status=project_status,
        start_date=start_date,
        due_date=due_date,
    )
    record(db, "PROJECT_CREATED", "Project", project.id, user_id=user.id, organization_id=organization_id, ip_address=request_ip(http_request))
    db.commit()
    return project_payload(project)


@router.get("")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if normalize_role_name(getattr(getattr(user, "role", None), "name", None)) == "super_admin":
        projects = project_repository.list_all(db)
    else:
        organization_roles = {
            membership.organization_id: normalize_role_name(membership.role)
            for membership in user.organization_memberships
            if membership.is_active
        }
        manager_organization_ids = [
            organization_id
            for organization_id, role in organization_roles.items()
            if role in {"org_admin", "admin", "project_manager"}
        ]
        visible_project_ids = [
            membership.project_id
            for membership in user.project_memberships
            if membership.is_active
            and organization_roles.get(membership.project.organization_id) in {"team_member", "viewer"}
        ]
        projects = project_repository.list_for_access_scope(db, manager_organization_ids, visible_project_ids)
    return [project_payload(project) for project in projects]


@router.get("/{project_id}")
def get_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_project_access(user, project)
    return project_payload(project)


@router.put("/{project_id}")
def update_project(project_id: int, request: ProjectUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    request = request.model_dump(exclude_unset=True)
    project = project_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_org_manager_access(user, project.organization_id)
    try:
        update_project_fields(project, request)
    except InvalidProjectStatusTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidProjectStatus as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    record(db, "PROJECT_UPDATED", "Project", project.id, user_id=user.id, organization_id=project.organization_id, metadata={"fields": sorted(request.keys())})
    db.commit()
    return project_payload(project)


@router.put("/{project_id}/archive")
def archive_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_org_manager_access(user, project.organization_id)
    try:
        archive_project_record(project)
    except InvalidProjectStatusTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    record(db, "PROJECT_ARCHIVED", "Project", project.id, user_id=user.id, organization_id=project.organization_id)
    db.commit()
    return {"id": project.id, "status": project.status}


@router.delete("/{project_id}")
def delete_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_org_manager_access(user, project.organization_id)
    record(db, "PROJECT_DELETED", "Project", project.id, user_id=user.id, organization_id=project.organization_id)
    delete_project_record(db, project)
    db.commit()
    return {"message": "Project deleted"}


@router.get("/{project_id}/members")
def list_project_members(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_org_manager_access(user, project.organization_id)
    members = project_repository.get_members(db, project_id)
    return [{"id": m.id, "project_id": m.project_id, "user_id": m.user_id} for m in members]


@router.post("/{project_id}/members")
def add_project_member(project_id: int, request: ProjectMemberCreate, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_org_manager_access(user, project.organization_id)
    target_user_id = request.user_id
    target_user = user_repository.get_by_id(db, target_user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not target_user.is_active or not any(member.organization_id == project.organization_id and member.is_active for member in target_user.organization_memberships):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User must belong to the same organization")
    existing = project_repository.get_member(db, project_id, target_user_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already in project")
    member = persist_project_member(db, project_id=project_id, user_id=target_user_id)
    record(db, "PROJECT_MEMBER_ADDED", "ProjectMember", member.id, user_id=user.id, organization_id=project.organization_id, metadata={"member_user_id": target_user_id})
    create_and_push_notification(
        db,
        background_tasks,
        user_id=target_user_id,
        notification_type="project_member_added",
        message=f"You were added to project '{project.name}'.",
    )
    db.commit()
    return {"id": member.id, "project_id": member.project_id, "user_id": member.user_id}


@router.delete("/{project_id}/members/{user_id}")
def remove_project_member(project_id: int, user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_org_manager_access(user, project.organization_id)
    member = project_repository.get_member(db, project_id, user_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project member not found")
    record(db, "PROJECT_MEMBER_REMOVED", "ProjectMember", member.id, user_id=user.id, organization_id=project.organization_id, metadata={"member_user_id": user_id})
    remove_project_member_record(db, member)
    db.commit()
    return {"message": "Project member removed"}
