from datetime import date
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import normalize_role_name
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.task import Task
from app.models.user import User
from app.services.audit_service import record
from app.services.authorization_service import (
    ensure_project_access,
    ensure_project_manager as ensure_project_manager_access,
    get_organization_role,
    ensure_task_access,
)
from app.services.task_dependency_service import (
    DependencyConflictError,
    DependencyScopeError,
    add_dependency as persist_dependency,
    list_dependencies as get_task_dependencies,
    remove_dependency as delete_task_dependency,
)
from app.repositories import project_repository, task_repository
from app.schemas.task import TaskAssignmentUpdate, TaskCreate, TaskDependencyCreate, TaskMoveRequest, TaskStatusUpdate, TaskUpdate
from app.services.task_service import (
    assign_task_to_user,
    create_project_task,
    delete_task as delete_task_record,
    normalize_status,
    move_task_to_project,
    transition_task,
    update_task_fields,
    validate_task_status,
    list_tasks_for_user,
)


def task_payload(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "project_id": task.project_id,
        "assignee_id": task.assignee_id,
        "reporter_id": task.reporter_id,
        "priority": task.priority,
        "status": task.status,
        "due_date": task.due_date,
        "estimated_hours": task.estimated_hours,
        "actual_hours": task.actual_hours,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


router = APIRouter()
dependency_router = APIRouter(prefix="/api/tasks", tags=["Task Dependencies"])



@router.post("/tasks")
def create_task(request: TaskCreate, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project_id = request.project_id
    project = project_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_project_access(user, project)
    ensure_project_manager_access(user, project)

    try:
        task = create_project_task(
            db,
            project,
            user,
            title=request.title,
            description=request.description,
            assignee_id=request.assignee_id,
            priority=request.priority,
            status=request.status,
            due_date=request.due_date,
            estimated_hours=request.estimated_hours,
            actual_hours=request.actual_hours,
            background_tasks=background_tasks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(task)
    return task_payload(task)


@router.get("/tasks")
def list_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    task_status: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    assignee_id: int | None = None,
    project: int | None = None,
    search: str | None = None,
    due_date_from: date | None = None,
    due_date_to: date | None = None,
    created_date_from: date | None = None,
    created_date_to: date | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        tasks, total = list_tasks_for_user(
            db,
            user,
            page=page,
            page_size=page_size,
            status=task_status,
            priority=priority,
            assignee_id=assignee_id,
            project_id=project,
            search=search,
            due_date_from=due_date_from,
            due_date_to=due_date_to,
            created_date_from=created_date_from,
            created_date_to=created_date_to,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return {
        "items": [task_payload(task) for task in tasks],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/tasks/{task_id}")
def get_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_task_access(user, task)
    return task_payload(task)


@router.put("/tasks/{task_id}")
def update_task(task_id: int, request: TaskUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    request = request.model_dump(exclude_unset=True)
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_project_access(user, task.project)
    ensure_project_manager_access(user, task.project)
    try:
        update_task_fields(task, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record(db, "TASK_UPDATED", "Task", task.id, user_id=user.id, organization_id=task.project.organization_id, metadata={"fields": sorted(request.keys())})
    db.commit()
    db.refresh(task)
    return task_payload(task)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_project_manager_access(user, task.project)
    record(db, "TASK_DELETED", "Task", task.id, user_id=user.id, organization_id=task.project.organization_id)
    delete_task_record(db, task, user)
    db.commit()
    return {"message": "Task deleted"}


@router.put("/tasks/{task_id}/reassign")
def reassign_task(task_id: int, request: TaskAssignmentUpdate, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_project_access(user, task.project)
    ensure_project_manager_access(user, task.project)
    try:
        assign_task_to_user(db, task, request.assignee_id, user, background_tasks)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return {"id": task.id, "assignee_id": task.assignee_id}


@router.put("/tasks/{task_id}/status")
def change_status(task_id: int, request: TaskStatusUpdate, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_task_access(user, task)
    role = get_organization_role(user, task.project.organization_id)
    if role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot change task status")
    if role == "team_member" and task.assignee_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Team members can only change the status of tasks assigned to them")
    new_status = normalize_status(request.status)
    try:
        new_status = validate_task_status(new_status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        transition_task(db, task, new_status, user, background_tasks)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    return {"id": task.id, "status": task.status}


@router.put("/tasks/{task_id}/move")
def move_task(task_id: int, request: TaskMoveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_project_manager_access(user, task.project)
    project_id = request.project_id
    target_project = project_repository.get_by_id(db, project_id)
    if not target_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target project not found")
    ensure_project_manager_access(user, target_project)
    try:
        move_task_to_project(db, task, target_project, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return {"id": task.id, "project_id": task.project_id}




@dependency_router.post("/{task_id}/dependencies")
def add_task_dependency(task_id: int, request: TaskDependencyCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_project_access(user, task.project)
    depends_on_task_id = request.depends_on_task_id
    depends_on_task = task_repository.get_by_id(db, depends_on_task_id)
    if depends_on_task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependent task not found")
    try:
        persist_dependency(db, task=task, depends_on_task=depends_on_task)
    except DependencyScopeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DependencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    return {"message": "Task dependency added"}


@dependency_router.get("/{task_id}/dependencies")
def list_task_dependencies(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_project_access(user, task.project)
    dependencies = [
        {
            "id": dependency["id"],
            "task_id": dependency["task_id"],
            "depends_on_task_id": dependency["depends_on_task_id"],
            "depends_on_title": dependency["depends_on_task"].title if dependency["depends_on_task"] else None,
            "status": dependency["depends_on_task"].status if dependency["depends_on_task"] else None,
        }
        for dependency in get_task_dependencies(db, task)
    ]
    return {"task_id": task_id, "dependencies": dependencies}


@dependency_router.delete("/{task_id}/dependencies/{dependency_id}")
def remove_task_dependency(task_id: int, dependency_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_project_access(user, task.project)
    if not delete_task_dependency(db, task, dependency_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")
    db.commit()
    return {"message": "Task dependency removed"}
