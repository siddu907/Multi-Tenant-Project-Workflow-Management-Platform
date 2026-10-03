from typing import Iterable

from fastapi import HTTPException, status

ROLE_ALIASES = {
    "super_admin": "super_admin",
    "superadmin": "super_admin",
    "org_admin": "org_admin",
    "organization_admin": "org_admin",
    "orgadmin": "org_admin",
    "admin": "org_admin",
    "project_manager": "project_manager",
    "projectmanager": "project_manager",
    "manager": "project_manager",
    "team_member": "team_member",
    "teammember": "team_member",
    "member": "team_member",
    "viewer": "viewer",
}


def normalize_role_name(value: str | None) -> str:
    if value is None:
        return ""
    key = str(value).strip().lower().replace(" ", "_")
    return ROLE_ALIASES.get(key, key)


def user_has_role(user, roles: Iterable[str]) -> bool:
    if not user:
        return False
    current = normalize_role_name(getattr(getattr(user, "role", None), "name", None))
    allowed = {normalize_role_name(role) for role in roles}
    return current in allowed


def require_roles(user, roles: Iterable[str]) -> None:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if not user_has_role(user, roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def require_org_member(user, organization_id: int) -> None:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    org_ids = {membership.organization_id for membership in getattr(user, "organization_memberships", [])}
    if organization_id not in org_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this organization")


def require_project_member(user, project_id: int) -> None:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    project_ids = {membership.project_id for membership in getattr(user, "project_memberships", []) if getattr(membership, "is_active", True)}
    if project_id not in project_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this project")
