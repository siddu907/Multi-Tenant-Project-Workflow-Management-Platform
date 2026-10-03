from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.repositories import organization_repository


def can_manage_organization(user, organization_id: int) -> bool:
    if not user:
        return False
    if getattr(user.role, "name", "").lower() in {"super_admin", "org_admin"}:
        return True
    return any(
        member.organization_id == organization_id and getattr(member, "role", "").lower() in {"org_admin", "admin"}
        for member in getattr(user, "organization_memberships", [])
    )


def create_organization(db: Session, *, name: str, description: str | None = None, owner_id: int | None):
    organization = organization_repository.create(db, name=name, description=description)
    db.flush()
    if owner_id is not None:
        organization_repository.add_member(db, organization.id, owner_id, role="org_admin", is_active=True)
    return organization


def update_organization(db: Session, organization: Organization, changes: dict) -> Organization:
    if changes.get("name"):
        organization.name = changes["name"].strip()
    if "description" in changes:
        organization.description = changes["description"]
    return organization


def create_member(db: Session, *, organization_id: int, user_id: int, role: str = "team_member"):
    return organization_repository.add_member(db, organization_id, user_id, role=role, is_active=True)


def update_member_role(member: OrganizationMember, role: str) -> OrganizationMember:
    member.role = role
    return member


def set_member_active(member: OrganizationMember, is_active: bool) -> OrganizationMember:
    member.is_active = is_active
    return member


def remove_member(db: Session, member: OrganizationMember) -> None:
    organization_repository.remove_member(db, member)


def delete_organization(db: Session, organization: Organization) -> None:
    organization_repository.remove_organization(db, organization)
