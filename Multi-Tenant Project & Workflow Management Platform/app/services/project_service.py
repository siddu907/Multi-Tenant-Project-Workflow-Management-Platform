from datetime import date

from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_member import ProjectMember
from app.repositories import project_repository

PROJECT_STATUS_TRANSITIONS = {
    "planning": {"active", "on_hold", "archived"},
    "active": {"on_hold", "completed", "archived"},
    "on_hold": {"active", "archived"},
    "completed": {"archived"},
    "archived": set(),
}


class InvalidProjectStatus(ValueError):
    pass


class InvalidProjectStatusTransition(ValueError):
    pass


def normalize_project_status(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def validate_project_status(value: str) -> str:
    normalized = normalize_project_status(value)
    if normalized not in PROJECT_STATUS_TRANSITIONS:
        raise InvalidProjectStatus("Invalid project status")
    return normalized


def validate_project_status_transition(current_status: str, new_status: str) -> str:
    normalized = validate_project_status(new_status)
    if normalized != current_status and normalized not in PROJECT_STATUS_TRANSITIONS[current_status]:
        raise InvalidProjectStatusTransition(
            f"Invalid project status transition from {current_status} to {normalized}"
        )
    return normalized


def validate_project_dates(start_date: date | None, due_date: date | None) -> None:
    if start_date is not None and due_date is not None and start_date > due_date:
        raise ValueError("Project start_date cannot be after due_date")


def create_project(
    db: Session,
    *,
    name: str,
    organization_id: int,
    owner_id: int,
    description: str | None = None,
    status: str = "planning",
    start_date: date | None = None,
    due_date: date | None = None,
) -> Project:
    validate_project_dates(start_date, due_date)
    project = Project(
        name=name,
        description=description,
        organization_id=organization_id,
        owner_id=owner_id,
        status=status,
        start_date=start_date,
        due_date=due_date,
    )
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=owner_id, is_active=True))
    return project


def update_project_fields(project: Project, changes: dict) -> Project:
    if changes.get("name") is not None:
        name = changes["name"].strip()
        if not name:
            raise ValueError("Project name is required")
        project.name = name
    if "description" in changes:
        project.description = changes["description"]
    if changes.get("status") is not None:
        project.status = validate_project_status_transition(project.status, changes["status"])
    if "start_date" in changes:
        project.start_date = changes["start_date"]
    if "due_date" in changes:
        project.due_date = changes["due_date"]
    validate_project_dates(project.start_date, project.due_date)
    return project


def archive_project(project: Project) -> Project:
    project.status = validate_project_status_transition(project.status, "archived")
    return project


def add_member(db: Session, *, project_id: int, user_id: int) -> ProjectMember:
    return project_repository.add_member(db, project_id=project_id, user_id=user_id, is_active=True)


def remove_member(db: Session, member: ProjectMember) -> None:
    project_repository.remove_member(db, member)


def delete_project(db: Session, project: Project) -> None:
    for task in list(project.tasks):
        db.delete(task)
    project_repository.delete(db, project)
