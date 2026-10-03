from fastapi import HTTPException, status


def require_organization_membership(user, organization_id: int) -> None:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    org_ids = {member.organization_id for member in getattr(user, "organization_memberships", [])}
    if organization_id not in org_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this organization")


def require_organization_admin(user, organization_id: int) -> None:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if getattr(user.role, "name", "").lower() in {"super_admin", "org_admin"}:
        return
    org_roles = {
        member.organization_id: getattr(member, "role", "").lower()
        for member in getattr(user, "organization_memberships", [])
    }
    if org_roles.get(organization_id) not in {"org_admin", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin permissions required")
