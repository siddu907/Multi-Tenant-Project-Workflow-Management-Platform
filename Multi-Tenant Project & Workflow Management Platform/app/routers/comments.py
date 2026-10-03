import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.services.audit_service import record
from app.services.notification_service import create_and_push_notification
from app.schemas.comment import CommentCreate, CommentUpdate
from app.services.authorization_service import ensure_project_access, ensure_task_comment_access as ensure_task_access, get_organization_role
from app.repositories import comment_repository, project_repository, task_repository, user_repository
from app.services.comment_service import create_comment, delete_comment as remove_comment, update_comment as edit_comment

router = APIRouter()
MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_.-]+(?:@[A-Za-z0-9_.-]+\.[A-Za-z]+)?)")


def notify_mentions(db: Session, background_tasks: BackgroundTasks, message: str, user: User, task: Task) -> None:
    mentioned = MENTION_PATTERN.findall(message)
    for handle in mentioned:
        match = user_repository.get_active_for_mention(db, handle)
        if match and match.id != user.id:
            belongs_to_org = any(
                member.organization_id == task.project.organization_id and member.is_active
                for member in match.organization_memberships
            )
            belongs_to_project = any(
                member.project_id == task.project_id and member.is_active for member in match.project_memberships
            )
            if belongs_to_org and belongs_to_project:
                create_and_push_notification(
                    db,
                    background_tasks,
                    user_id=match.id,
                    notification_type="mention",
                    message=f"{user.name} mentioned you on task #{task.id}",
                )


def ensure_project_comment_access(user: User, project: Project) -> None:
    ensure_project_access(user, project)


def notify_project_mentions(db: Session, background_tasks: BackgroundTasks, message: str, user: User, project: Project) -> None:
    for handle in MENTION_PATTERN.findall(message):
        mentioned = user_repository.get_active_for_mention(db, handle)
        if mentioned is None or mentioned.id == user.id:
            continue
        if not any(member.organization_id == project.organization_id and member.is_active for member in mentioned.organization_memberships):
            continue
        if not any(member.project_id == project.id and member.is_active for member in mentioned.project_memberships):
            continue
        create_and_push_notification(
            db,
            background_tasks,
            user_id=mentioned.id,
            notification_type="mention",
            message=f"{user.name} mentioned you in project '{project.name}'.",
        )


@router.post("/tasks/{task_id}/comments")
def add_comment(task_id: int, request: CommentCreate, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_task_access(user, task)
    if get_organization_role(user, task.project.organization_id) == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot add comments")
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment content is required")
    comment = create_comment(db, content=content, user_id=user.id, task_id=task.id)
    notify_mentions(db, background_tasks, content, user, task)
    record(db, "COMMENT_ADDED", "Comment", comment.id, user_id=user.id, organization_id=task.project.organization_id, metadata={"task_id": task.id})
    recipients = {task.assignee_id, task.reporter_id} - {None, user.id}
    recipients.update(project_repository.list_active_member_user_ids(db, task.project_id))
    recipients.discard(user.id)
    for recipient_id in recipients:
        create_and_push_notification(
            db,
            background_tasks,
            user_id=recipient_id,
            notification_type="comment_added",
            message=f"New comment on task '{task.title}'.",
        )
    db.commit()
    return {"id": comment.id, "content": comment.content, "task_id": comment.task_id, "user_id": comment.user_id}


@router.get("/tasks/{task_id}/comments")
def list_comments(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_task_access(user, task)
    comments = comment_repository.list_for_task(db, task_id)
    return [{"id": c.id, "content": c.content, "user_id": c.user_id, "task_id": c.task_id} for c in comments]


@router.post("/projects/{project_id}/comments")
def add_project_comment(project_id: int, request: CommentCreate, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_repository.get_by_id(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_project_comment_access(user, project)
    if get_organization_role(user, project.organization_id) == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot add comments")
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment content is required")
    comment = create_comment(db, content=content, user_id=user.id, project_id=project.id)
    notify_project_mentions(db, background_tasks, content, user, project)
    record(db, "COMMENT_ADDED", "Comment", comment.id, user_id=user.id, organization_id=project.organization_id, metadata={"project_id": project.id})
    project_member_ids = project_repository.list_active_member_user_ids(db, project.id)
    for recipient_id in set(project_member_ids) - {user.id}:
        create_and_push_notification(
            db,
            background_tasks,
            user_id=recipient_id,
            notification_type="comment_added",
            message=f"New comment on project '{project.name}'.",
        )
    db.commit()
    return {"id": comment.id, "content": comment.content, "project_id": comment.project_id, "user_id": comment.user_id}


@router.get("/projects/{project_id}/comments")
def list_project_comments(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_repository.get_by_id(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_project_comment_access(user, project)
    comments = comment_repository.list_for_project(db, project_id)
    return [{"id": comment.id, "content": comment.content, "user_id": comment.user_id, "project_id": comment.project_id} for comment in comments]


@router.put("/comments/{comment_id}")
def update_comment(comment_id: int, request: CommentUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    comment = comment_repository.get_by_id(db, comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    if comment.task_id is not None:
        task = task_repository.get_by_id(db, comment.task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment resource not found")
        ensure_task_access(user, task)
    elif comment.project_id is not None:
        project = project_repository.get_by_id(db, comment.project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment resource not found")
        ensure_project_comment_access(user, project)
    if comment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can update a comment")
    edit_comment(comment, request.content.strip())
    db.commit()
    return {"id": comment.id, "content": comment.content}


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    comment = comment_repository.get_by_id(db, comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    if comment.task_id is not None:
        task = task_repository.get_by_id(db, comment.task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment resource not found")
        ensure_task_access(user, task)
    elif comment.project_id is not None:
        project = project_repository.get_by_id(db, comment.project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment resource not found")
        ensure_project_comment_access(user, project)
    if comment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can delete a comment")
    remove_comment(db, comment)
    db.commit()
    return {"message": "Comment deleted"}
