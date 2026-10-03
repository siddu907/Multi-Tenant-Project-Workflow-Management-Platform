from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.organization_member import OrganizationMember
from app.models.task import Task
from app.models.user import User


def get_organization_dashboard(db: Session, organization_ids: list[int]):
    if not organization_ids:
        return {
            "total_projects": 0,
            "active_projects": 0,
            "completed_projects": 0,
            "total_users": 0,
            "active_users": 0,
            "total_tasks": 0,
            "overdue_tasks": 0,
        }
    total_projects = db.scalar(select(func.count(Project.id)).where(Project.organization_id.in_(organization_ids))) or 0
    active_projects = db.scalar(select(func.count(Project.id)).where(Project.organization_id.in_(organization_ids), Project.status == "active")) or 0
    completed_projects = db.scalar(select(func.count(Project.id)).where(Project.organization_id.in_(organization_ids), Project.status == "completed")) or 0
    total_tasks = db.scalar(select(func.count(Task.id)).join(Project).where(Project.organization_id.in_(organization_ids))) or 0
    overdue_tasks = db.scalar(select(func.count(Task.id)).join(Project).where(Project.organization_id.in_(organization_ids), Task.due_date < date.today(), Task.status.notin_(["done", "cancelled"]))) or 0
    total_users = db.scalar(
        select(func.count(func.distinct(OrganizationMember.user_id))).where(
            OrganizationMember.organization_id.in_(organization_ids)
        )
    ) or 0
    active_users = db.scalar(
        select(func.count(func.distinct(OrganizationMember.user_id)))
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id.in_(organization_ids),
            OrganizationMember.is_active.is_(True),
            User.is_active.is_(True),
        )
    ) or 0
    return {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "completed_projects": completed_projects,
        "total_users": total_users,
        "active_users": active_users,
        "total_tasks": total_tasks,
        "overdue_tasks": overdue_tasks,
    }


def get_project_manager_dashboard(db: Session, organization_ids: list[int]):
    if not organization_ids:
        return {
            "my_projects": 0,
            "open_tasks": 0,
            "completed_tasks": 0,
            "overdue_tasks": 0,
            "tasks_by_member": [],
            "tasks_by_priority": [],
        }
    my_projects = db.scalar(select(func.count(Project.id)).where(Project.organization_id.in_(organization_ids))) or 0
    open_tasks = db.scalar(
        select(func.count(Task.id)).join(Project).where(
            Project.organization_id.in_(organization_ids),
            Task.status.in_(["backlog", "todo", "in_progress", "review", "blocked"]),
        )
    ) or 0
    completed_tasks = db.scalar(
        select(func.count(Task.id)).join(Project).where(
            Project.organization_id.in_(organization_ids), Task.status == "done"
        )
    ) or 0
    overdue_tasks = db.scalar(
        select(func.count(Task.id)).join(Project).where(
            Project.organization_id.in_(organization_ids),
            Task.due_date < date.today(),
            Task.status.notin_(["done", "cancelled"]),
        )
    ) or 0
    tasks_by_member = db.execute(
        select(Task.project_id, Task.assignee_id, User.name, func.count(Task.id))
        .join(Project, Task.project_id == Project.id)
        .outerjoin(User, User.id == Task.assignee_id)
        .where(Project.organization_id.in_(organization_ids))
        .group_by(Task.project_id, Task.assignee_id, User.name)
    ).all()
    tasks_by_priority = db.execute(
        select(Task.priority, func.count(Task.id))
        .join(Project, Task.project_id == Project.id)
        .where(Project.organization_id.in_(organization_ids))
        .group_by(Task.priority)
    ).all()
    return {
        "my_projects": my_projects,
        "open_tasks": open_tasks,
        "completed_tasks": completed_tasks,
        "overdue_tasks": overdue_tasks,
        "tasks_by_member": [
            {"project_id": project_id, "assignee_id": assignee_id, "assignee_name": name, "task_count": count}
            for project_id, assignee_id, name, count in tasks_by_member
        ],
        "tasks_by_priority": [
            {"priority": priority, "task_count": count}
            for priority, count in tasks_by_priority
        ],
    }


def get_my_tasks_dashboard(db: Session, user_id: int, project_ids: list[int]):
    tasks = db.scalars(
        select(Task).where(Task.assignee_id == user_id, Task.project_id.in_(project_ids))
        if project_ids
        else select(Task).where(False)
    ).all()
    today = date.today()
    recently = datetime.now(timezone.utc) - timedelta(days=7)
    overdue = sum(1 for task in tasks if task.status not in {"done", "cancelled"} and task.due_date is not None and task.due_date < today)
    due_today = sum(1 for task in tasks if task.status not in {"done", "cancelled"} and task.due_date == today)
    completed = sum(1 for task in tasks if task.status == "done" and task.updated_at.replace(tzinfo=timezone.utc) >= recently)
    return {
        "my_tasks": len(tasks),
        "overdue_tasks": overdue,
        "tasks_due_today": due_today,
        "recently_completed_tasks": completed,
    }
