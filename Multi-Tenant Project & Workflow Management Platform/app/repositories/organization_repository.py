from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember


def create(db: Session, *, name: str, description: str | None = None) -> Organization:
    organization = Organization(name=name, description=description)
    db.add(organization)
    db.flush()
    return organization


def get_by_id(db: Session, organization_id: int):
    return db.get(Organization, organization_id)


def list_for_user(db: Session, user_id: int):
    return db.scalars(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user_id, OrganizationMember.is_active.is_(True))
        .order_by(Organization.name.asc())
    ).all()


def list_all(db: Session):
    return db.scalars(select(Organization).order_by(Organization.name.asc())).all()


def list_ids(db: Session) -> list[int]:
    return db.scalars(select(Organization.id)).all()


def get_member(db: Session, organization_id: int, user_id: int):
    return db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )


def get_members(db: Session, organization_id: int):
    return db.scalars(
        select(OrganizationMember).where(OrganizationMember.organization_id == organization_id)
    ).all()


def add_member(db: Session, organization_id: int, user_id: int, role: str = "team_member", is_active: bool = True):
    member = OrganizationMember(organization_id=organization_id, user_id=user_id, role=role, is_active=is_active)
    db.add(member)
    db.flush()
    return member


def remove_member(db: Session, member: OrganizationMember):
    db.delete(member)
    return member


def remove_organization(db: Session, organization: Organization):
    db.delete(organization)
