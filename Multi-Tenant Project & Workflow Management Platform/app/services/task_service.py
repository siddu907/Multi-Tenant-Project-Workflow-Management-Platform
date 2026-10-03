from typing import Any

from fastapi import BackgroundTasks

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import normalize_role_name
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.task_dependency import TaskDependency
from app.models.user import User
from app.repositories import task_repository
from app.services.audit_service import record
from app.services.notification_service import create_and_push_notification

VALID_TASK_STATUSES = {"backlog", "todo", "in_progress", "review", "blocked", "done", "cancelled"}
VALID_STATUS_TRANSITIONS = {
    "backlog": {"todo", "cancelled"},
    "todo": {"in_progress", "blocked", "cancelled"},
    "in_progress": {"review", "blocked", "todo"},
    "blocked": {"todo", "in_progress", "cancelled"},
    "review": {"done", "in_progress", "blocked"},
    "done": set(),
    "cancelled": set(),
}


def normalize_status(value: Any) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def validate_task_status(value: str) -> str:
    normalized = normalize_status(value)
    if normalized not in VALID_TASK_STATUSES:
        raise ValueError("Invalid status")
    return normalized


def can_transition(current_status: str, new_status: str) -> bool:
    return normalize_status(new_status) in VALID_STATUS_TRANSITIONS.get(normalize_status(current_status), set())


def create_task(db: Session, **kwargs) -> Task:
    return task_repository.create(db, **kwargs)


def validate_priority(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in {"low", "medium", "high", "urgent"}:
        raise ValueError("Invalid task priority")
    return normalized


def create_project_task(
    db: Session,
    project: Project,
    reporter: User,
    *,
    title: str,
    description: str | None,
    assignee_id: int | None,
    priority: str,
    status: str,
    due_date,
    estimated_hours: float | None,
    actual_hours: float | None,
    background_tasks: BackgroundTasks,
) -> Task:
    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("Task title is required")
    normalized_status = normalize_status(status)
    if normalized_status not in VALID_TASK_STATUSES:
        raise ValueError("Invalid task status")
    normalized_priority = validate_priority(priority)
    if assignee_id is not None:
        get_assignable_user(db, project, assignee_id)
    task = create_task(
        db,
        title=normalized_title,
        description=description,
        project_id=project.id,
        assignee_id=assignee_id,
        reporter_id=reporter.id,
        priority=normalized_priority,
        status=normalized_status,
        due_date=due_date,
        estimated_hours=estimated_hours,
        actual_hours=actual_hours,
    )
    record(db, "TASK_CREATED", "Task", task.id, user_id=reporter.id, organization_id=project.organization_id)
    if task.assignee_id is not None:
        create_and_push_notification(
            db,
            background_tasks,
            user_id=task.assignee_id,
            notification_type="task_assigned",
            message=f"You were assigned task '{task.title}'.",
        )
    return task


def update_task_fields(task: Task, changes: dict[str, Any]) -> Task:
    if changes.get("title") is not None:
        title = changes["title"].strip()
        if not title:
            raise ValueError("Task title is required")
        task.title = title
    if "description" in changes:
        task.description = changes["description"]
    if changes.get("priority") is not None:
        task.priority = validate_priority(changes["priority"])
    if "due_date" in changes:
        task.due_date = changes["due_date"]
    if "estimated_hours" in changes:
        task.estimated_hours = changes["estimated_hours"]
    if "actual_hours" in changes:
        task.actual_hours = changes["actual_hours"]
    return task


def assign_task_to_user(
    db: Session,
    task: Task,
    assignee_id: int,
    actor: User,
    background_tasks: BackgroundTasks,
) -> Task:
    assignee = get_assignable_user(db, task.project, assignee_id)
    previous_assignee_id = task.assignee_id
    task.assignee_id = assignee_id
    record(
        db,
        "TASK_ASSIGNED",
        "Task",
        task.id,
        user_id=actor.id,
        organization_id=task.project.organization_id,
        metadata={"previous_assignee_id": previous_assignee_id, "assignee_id": assignee_id},
    )
    if previous_assignee_id != assignee_id:
        notification_type = "task_reassigned" if previous_assignee_id is not None else "task_assigned"
        if previous_assignee_id is not None:
            create_and_push_notification(
                db,
                background_tasks,
                user_id=previous_assignee_id,
                notification_type="task_reassigned",
                message=f"Task '{task.title}' was reassigned to {assignee.name}.",
            )
        create_and_push_notification(
            db,
            background_tasks,
            user_id=assignee_id,
            notification_type=notification_type,
            message=f"You were assigned task '{task.title}'.",
        )
    return task


def get_assignable_user(db: Session, project: Project, user_id: int) -> User:
    assignee = db.get(User, user_id)
    if assignee is None or not assignee.is_active:
        raise ValueError("Assignee must be an active user")
    tenant_roles = {
        normalize_role_name(membership.role)
        for membership in assignee.organization_memberships
        if membership.organization_id == project.organization_id and membership.is_active
    }
    if "viewer" in tenant_roles:
        raise ValueError("Viewers cannot be assigned tasks")
    if not tenant_roles:
        raise ValueError("Assignee must belong to the same organization")
    project_member = db.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == assignee.id,
            ProjectMember.is_active.is_(True),
        )
    )
    if project_member is None:
        raise ValueError("Assignee must be an active member of the project")
    return assignee


def update_task_status(task: Task, new_status: str) -> Task:
    normalized = normalize_status(new_status)
    if normalized not in VALID_TASK_STATUSES:
        raise ValueError(f"Invalid task status: {new_status}")
    if not can_transition(task.status, normalized):
        raise ValueError(f"Invalid status transition from {task.status} to {normalized}")
    task.status = normalized
    return task


def validate_status_transition(db: Session, task: Task, new_status: str) -> str:
    normalized = validate_task_status(new_status)
    if not can_transition(task.status, normalized):
        raise ValueError(f"Invalid status transition from {task.status} to {normalized}")
    if normalized in {"in_progress", "review", "done"}:
        unfinished_dependency = db.scalar(
            select(Task.id)
            .join(TaskDependency, TaskDependency.depends_on_task_id == Task.id)
            .where(TaskDependency.task_id == task.id, Task.status != "done")
        )
        if unfinished_dependency is not None:
            raise ValueError("Task dependencies must be completed before this status transition")
    return normalized


def transition_task(
    db: Session,
    task: Task,
    new_status: str,
    actor: User,
    background_tasks: BackgroundTasks,
) -> Task:
    normalized = validate_status_transition(db, task, new_status)
    previous_status = task.status
    task.status = normalized
    record(
        db,
        "TASK_STATUS_CHANGED",
        "Task",
        task.id,
        user_id=actor.id,
        organization_id=task.project.organization_id,
        metadata={"from": previous_status, "to": normalized},
    )
    if task.assignee_id is not None and task.assignee_id != actor.id:
        create_and_push_notification(
            db,
            background_tasks,
            user_id=task.assignee_id,
            notification_type="task_status_changed",
            message=f"Task '{task.title}' changed from {previous_status} to {normalized}.",
        )
    return task


def move_task_to_project(db: Session, task: Task, target_project: Project, actor: User) -> Task:
    if target_project.organization_id != task.project.organization_id:
        raise ValueError("Tasks can only move between projects in the same organization")
    if task.assignee_id is not None:
        membership = db.scalar(
            select(ProjectMember.id).where(
                ProjectMember.project_id == target_project.id,
                ProjectMember.user_id == task.assignee_id,
                ProjectMember.is_active.is_(True),
            )
        )
        if membership is None:
            raise ValueError("The current assignee is not a member of the target project")
    task.project_id = target_project.id
    record(
        db,
        "TASK_MOVED",
        "Task",
        task.id,
        user_id=actor.id,
        organization_id=target_project.organization_id,
        metadata={"project_id": target_project.id},
    )
    return task


def delete_task(db: Session, task: Task, actor: User) -> None:
    record(db, "TASK_DELETED", "Task", task.id, user_id=actor.id, organization_id=task.project.organization_id)
    task_repository.delete(db, task)


def list_tasks_for_user(
    db: Session,
    user: User,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: int | None = None,
    project_id: int | None = None,
    search: str | None = None,
    due_date_from=None,
    due_date_to=None,
    created_date_from=None,
    created_date_to=None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    role = normalize_role_name(user.role.name if user.role else None)
    if role == "super_admin":
        visibility, organization_ids, project_ids, assigned_project_ids = "all", [], [], []
    else:
        organization_roles = {
            membership.organization_id: normalize_role_name(membership.role)
            for membership in user.organization_memberships
            if membership.is_active
        }
        organization_ids = [
            organization_id
            for organization_id, organization_role in organization_roles.items()
            if organization_role in {"org_admin", "admin", "project_manager"}
        ]
        project_ids = []
        assigned_project_ids = []
        for membership in user.project_memberships:
            if not membership.is_active:
                continue
            organization_role = organization_roles.get(membership.project.organization_id)
            if organization_role == "viewer":
                project_ids.append(membership.project_id)
            elif organization_role == "team_member":
                assigned_project_ids.append(membership.project_id)
        visibility = "organization_roles"

    normalized_status = normalize_status(status) if status else None
    return task_repository.list_filtered(
        db,
        visibility=visibility,
        user_id=user.id,
        organization_ids=organization_ids,
        project_ids=project_ids,
        assigned_project_ids=assigned_project_ids,
        page=page,
        page_size=page_size,
        status=normalized_status,
        priority=priority,
        assignee_id=assignee_id,
        project_id=project_id,
        search=search,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        created_date_from=created_date_from,
        created_date_to=created_date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
