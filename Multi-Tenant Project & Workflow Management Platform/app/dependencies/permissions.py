from fastapi import HTTPException, status


def require_roles(user, allowed_roles: set[str]) -> None:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if getattr(user.role, "name", "").lower() not in {role.lower() for role in allowed_roles}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def require_project_access(user, project) -> None:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if getattr(user.role, "name", "").lower() == "super_admin":
        return
    org_ids = {member.organization_id for member in getattr(user, "organization_memberships", [])}
    if project.organization_id not in org_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this project")
