from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.task_dependency import TaskDependency


class DependencyScopeError(ValueError):
    pass


class DependencyConflictError(ValueError):
    pass


def has_circular_dependency(db: Session, task_id: int, depends_on_task_id: int) -> bool:
    if task_id == depends_on_task_id:
        return True
    visited: set[int] = set()
    stack = [depends_on_task_id]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        if current == task_id:
            return True
        dependencies = db.scalars(select(TaskDependency).where(TaskDependency.task_id == current)).all()
        stack.extend(dep.depends_on_task_id for dep in dependencies)
    return False


def dependency_exists(db: Session, task_id: int, depends_on_task_id: int) -> bool:
    return db.scalar(
        select(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.depends_on_task_id == depends_on_task_id,
        )
    ) is not None


def add_dependency(db: Session, *, task: Task, depends_on_task: Task):
    if task.project_id != depends_on_task.project_id:
        raise DependencyScopeError("Dependencies must be within the same project")
    if task.status in {"done", "cancelled"}:
        raise DependencyConflictError("Completed or cancelled tasks cannot depend on new tasks")
    if dependency_exists(db, task.id, depends_on_task.id):
        raise DependencyConflictError("Dependency already exists")
    if has_circular_dependency(db, task.id, depends_on_task.id):
        raise DependencyConflictError("Circular dependency is not allowed")
    relation = TaskDependency(task_id=task.id, depends_on_task_id=depends_on_task.id)
    db.add(relation)
    db.flush()
    return relation


def list_dependencies(db: Session, task: Task):
    dependencies = db.scalars(select(TaskDependency).where(TaskDependency.task_id == task.id)).all()
    return [
        {
            "id": dependency.id,
            "task_id": task.id,
            "depends_on_task_id": dependency.depends_on_task_id,
            "depends_on_task": db.get(Task, dependency.depends_on_task_id),
        }
        for dependency in dependencies
    ]


def remove_dependency(db: Session, task: Task, dependency_id: int) -> bool:
    dependency = db.scalar(
        select(TaskDependency).where(
            TaskDependency.id == dependency_id,
            TaskDependency.task_id == task.id,
        )
    )
    if dependency is None:
        return False
    db.delete(dependency)
    return True
