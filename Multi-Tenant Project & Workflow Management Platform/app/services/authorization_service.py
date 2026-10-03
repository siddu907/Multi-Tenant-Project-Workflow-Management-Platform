from fastapi import HTTPException, status

from app.core.permissions import normalize_role_name
from app.models.project import Project
from app.models.task import Task
from app.models.user import User


def get_organization_role(user: User, organization_id: int) -> str:
    if normalize_role_name(user.role.name if user.role else None) == "super_admin":
        return "super_admin"
    for membership in user.organization_memberships:
        if membership.organization_id == organization_id and membership.is_active:
            return normalize_role_name(membership.role)
    return ""


def has_active_organization_membership(user: User, organization_id: int) -> bool:
    return any(
        membership.organization_id == organization_id and membership.is_active
        for membership in user.organization_memberships
    )


def ensure_organization_admin(user: User, organization_id: int) -> None:
    if get_organization_role(user, organization_id) in {"super_admin", "org_admin", "admin"}:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin permissions required")


def ensure_organization_access(user: User, organization_id: int) -> None:
    if get_organization_role(user, organization_id):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not belong to this organization")


def ensure_organization_manager(user: User, organization_id: int) -> None:
    if get_organization_role(user, organization_id) in {"super_admin", "org_admin", "admin", "project_manager"}:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project management permissions required")


def ensure_project_access(user: User, project: Project) -> None:
    role = get_organization_role(user, project.organization_id)
    if role == "super_admin":
        return
    if role in {"org_admin", "admin", "project_manager"}:
        return
    if role and any(
        membership.project_id == project.id and membership.is_active
        for membership in user.project_memberships
    ):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this project")


def ensure_project_manager(user: User, project: Project) -> None:
    ensure_organization_manager(user, project.organization_id)


def ensure_task_access(user: User, task: Task) -> None:
    if task.project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_project_access(user, task.project)
    role = get_organization_role(user, task.project.organization_id)
    if role in {"super_admin", "org_admin", "admin", "project_manager"}:
        return
    if role == "team_member" and (task.assignee_id == user.id or task.reporter_id == user.id):
        return
    if role == "viewer" and any(
        membership.project_id == task.project_id and membership.is_active
        for membership in user.project_memberships
    ):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this task")


def ensure_task_comment_access(user: User, task: Task) -> None:
    ensure_project_access(user, task.project)
    role = get_organization_role(user, task.project.organization_id)
    if role == "super_admin":
        return
    if role in {"org_admin", "admin", "project_manager"}:
        return
    project_member = any(
        membership.project_id == task.project_id and membership.is_active
        for membership in user.project_memberships
    )
    if project_member and (role == "viewer" or (role == "team_member" and task.assignee_id == user.id)):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this task")


