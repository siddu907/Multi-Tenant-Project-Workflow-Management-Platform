from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.project_member import ProjectMember

def get_by_id(db: Session, project_id: int):
    return db.get(Project, project_id)


def delete(db: Session, project: Project) -> None:
    db.delete(project)


def list_all(db: Session):
    return db.scalars(select(Project).order_by(Project.name.asc())).all()


def list_for_organization(db: Session, organization_id: int):
    return db.scalars(
        select(Project).where(Project.organization_id == organization_id).order_by(Project.name.asc())
    ).all()


def list_for_user(db: Session, organization_ids: list[int]):
    if not organization_ids:
        return []
    return db.scalars(
        select(Project).where(Project.organization_id.in_(organization_ids)).order_by(Project.name.asc())
    ).all()


def list_for_project_ids(db: Session, project_ids: list[int]):
    if not project_ids:
        return []
    return db.scalars(select(Project).where(Project.id.in_(project_ids)).order_by(Project.name.asc())).all()


def list_for_access_scope(db: Session, organization_ids: list[int], project_ids: list[int]):
    access_scopes = []
    if organization_ids:
        access_scopes.append(Project.organization_id.in_(organization_ids))
    if project_ids:
        access_scopes.append(Project.id.in_(project_ids))
    if not access_scopes:
        return []
    return db.scalars(select(Project).where(or_(*access_scopes)).order_by(Project.name.asc())).all()


def get_members(db: Session, project_id: int):
    return db.scalars(select(ProjectMember).where(ProjectMember.project_id == project_id)).all()


def list_active_member_user_ids(db: Session, project_id: int) -> list[int]:
    return db.scalars(
        select(ProjectMember.user_id).where(
            ProjectMember.project_id == project_id,
            ProjectMember.is_active.is_(True),
        )
    ).all()


def add_member(db: Session, project_id: int, user_id: int, is_active: bool = True):
    member = ProjectMember(project_id=project_id, user_id=user_id, is_active=is_active)
    db.add(member)
    db.flush()
    return member


def get_member(db: Session, project_id: int, user_id: int):
    return db.scalar(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )


def remove_member(db: Session, member: ProjectMember):
    db.delete(member)
    return member
