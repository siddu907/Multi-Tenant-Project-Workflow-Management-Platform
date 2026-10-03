from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.role import Role
from app.models.user import User

def get_role_by_name(db: Session, name: str):
    return db.scalar(select(Role).where(Role.name == name))


def get_by_email(db: Session, email: str):
    return db.scalar(select(User).where(User.email == email.lower()))


def get_by_id(db: Session, user_id: int):
    return db.get(User, user_id)


def list_all(db: Session):
    return db.scalars(select(User).order_by(User.name.asc())).all()


def list_for_organizations(db: Session, organization_ids: list[int]):
    if not organization_ids:
        return []
    return db.scalars(
        select(User)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .where(
            OrganizationMember.organization_id.in_(organization_ids),
            OrganizationMember.is_active.is_(True),
        )
        .distinct()
        .order_by(User.name.asc())
    ).all()


def get_for_organizations(db: Session, user_id: int, organization_ids: list[int]):
    if not organization_ids:
        return None
    return db.scalar(
        select(User)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .where(
            User.id == user_id,
            OrganizationMember.organization_id.in_(organization_ids),
            OrganizationMember.is_active.is_(True),
        )
    )


def get_active_for_mention(db: Session, handle: str):
    normalized = handle.lower()
    normalized_name = func.lower(func.replace(User.name, " ", "_"))
    return db.scalar(
        select(User).where(
            User.is_active.is_(True),
            or_(User.email == normalized, normalized_name == normalized),
        )
    )


def get_user_memberships(db: Session, user_id: int):
    return db.scalars(select(OrganizationMember).where(OrganizationMember.user_id == user_id)).all()


def get_organization_members(db: Session, organization_id: int):
    return db.scalars(select(OrganizationMember).where(OrganizationMember.organization_id == organization_id)).all()


def get_organization_by_id(db: Session, organization_id: int):
    return db.get(Organization, organization_id)


def get_active_orgs_for_user(db: Session, user_id: int):
    return db.scalars(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user_id)
    ).all()
