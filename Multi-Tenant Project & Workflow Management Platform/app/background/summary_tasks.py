from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.task import Task


def build_project_summary(db: Session, project_id: int) -> dict:
    total_tasks = db.scalar(select(func.count(Task.id)).where(Task.project_id == project_id)) or 0
    done_tasks = db.scalar(select(func.count(Task.id)).where(Task.project_id == project_id, Task.status == "done")) or 0
    open_tasks = max(total_tasks - done_tasks, 0)
    project = db.get(Project, project_id)
    return {
        "project_id": project_id,
        "project_name": project.name if project else None,
        "total_tasks": total_tasks,
        "done_tasks": done_tasks,
        "open_tasks": open_tasks,
    }


def build_organization_summary(db: Session, organization_id: int) -> dict:
    total_projects = db.scalar(select(func.count(Project.id)).where(Project.organization_id == organization_id)) or 0
    total_tasks = db.scalar(
        select(func.count(Task.id)).join(Project, Task.project_id == Project.id).where(Project.organization_id == organization_id)
    ) or 0
    completed_tasks = db.scalar(
        select(func.count(Task.id)).join(Project, Task.project_id == Project.id).where(Project.organization_id == organization_id, Task.status == "done")
    ) or 0
    return {
        "organization_id": organization_id,
        "total_projects": total_projects,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
    }
