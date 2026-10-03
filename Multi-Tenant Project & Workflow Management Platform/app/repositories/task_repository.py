from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.task import Task
from app.models.task_dependency import TaskDependency


def create(db: Session, **values) -> Task:
    task = Task(**values)
    db.add(task)
    db.flush()
    return task


def get_by_id(db: Session, task_id: int):
    return db.get(Task, task_id)


def delete(db: Session, task: Task) -> None:
    db.delete(task)


def list_for_project(db: Session, project_id: int):
    return db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.created_at.desc())).all()


def list_for_organization(db: Session, organization_id: int):
    return db.scalars(
        select(Task).join(Project, Task.project_id == Project.id).where(Project.organization_id == organization_id)
    ).all()


def list_filtered(
    db: Session,
    *,
    visibility: str,
    user_id: int,
    organization_ids: list[int],
    project_ids: list[int],
    assigned_project_ids: list[int],
    page: int,
    page_size: int,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: int | None = None,
    project_id: int | None = None,
    search: str | None = None,
    due_date_from: date | None = None,
    due_date_to: date | None = None,
    created_date_from: date | None = None,
    created_date_to: date | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    query = select(Task)
    if visibility == "organizations":
        query = query.join(Project).where(Project.organization_id.in_(organization_ids))
    elif visibility == "manager_scope":
        manager_scopes = []
        if organization_ids:
            manager_scopes.append(Project.organization_id.in_(organization_ids))
        if project_ids:
            manager_scopes.append(Task.project_id.in_(project_ids))
        query = query.join(Project).where(or_(*manager_scopes)) if manager_scopes else query.where(False)
    elif visibility == "organization_roles":
        role_scopes = []
        if organization_ids:
            role_scopes.append(Project.organization_id.in_(organization_ids))
        if project_ids:
            role_scopes.append(Task.project_id.in_(project_ids))
        if assigned_project_ids:
            role_scopes.append(and_(Task.project_id.in_(assigned_project_ids), Task.assignee_id == user_id))
        query = query.join(Project).where(or_(*role_scopes)) if role_scopes else query.where(False)
    elif visibility == "assigned_projects":
        query = query.where(Task.assignee_id == user_id, Task.project_id.in_(project_ids)) if project_ids else query.where(False)
    elif visibility == "project_members":
        query = query.where(Task.project_id.in_(project_ids)) if project_ids else query.where(False)
    elif visibility != "all":
        query = query.where(False)

    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority.lower())
    if assignee_id is not None:
        query = query.where(Task.assignee_id == assignee_id)
    if project_id is not None:
        query = query.where(Task.project_id == project_id)
    if search:
        query = query.where(Task.title.ilike(f"%{search}%"))
    if due_date_from:
        query = query.where(Task.due_date >= due_date_from)
    if due_date_to:
        query = query.where(Task.due_date <= due_date_to)
    if created_date_from:
        query = query.where(Task.created_at >= datetime.combine(created_date_from, time.min))
    if created_date_to:
        query = query.where(Task.created_at < datetime.combine(created_date_to + timedelta(days=1), time.min))

    sort_columns = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.due_date,
        "title": Task.title,
        "priority": Task.priority,
        "status": Task.status,
    }
    sort_column = sort_columns.get(sort_by)
    if sort_column is None or sort_order.lower() not in {"asc", "desc"}:
        raise ValueError("Invalid task sort field or order")
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    ordered = sort_column.asc() if sort_order.lower() == "asc" else sort_column.desc()
    tasks = db.scalars(query.order_by(ordered).offset((page - 1) * page_size).limit(page_size)).all()
    return tasks, total


def get_dependencies(db: Session, task_id: int):
    return db.scalars(select(TaskDependency).where(TaskDependency.task_id == task_id)).all()


def add_dependency(db: Session, task_id: int, depends_on_task_id: int):
    relation = TaskDependency(task_id=task_id, depends_on_task_id=depends_on_task_id)
    db.add(relation)
    db.flush()
    return relation


def remove_dependency(db: Session, task_id: int, depends_on_task_id: int):
    dependency = db.scalar(
        select(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.depends_on_task_id == depends_on_task_id,
        )
    )
    if dependency:
        db.delete(dependency)
    return dependency


def count_by_status(db: Session, organization_id: int | None = None, status: str | None = None):
    query = select(Task)
    if organization_id is not None:
        query = query.join(Project, Task.project_id == Project.id).where(Project.organization_id == organization_id)
    if status is not None:
        query = query.where(Task.status == status)
    return db.scalar(select(len(db.scalars(query).all())))
