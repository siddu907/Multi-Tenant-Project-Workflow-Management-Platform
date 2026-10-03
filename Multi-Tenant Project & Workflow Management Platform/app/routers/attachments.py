import os
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.core.permissions import normalize_role_name
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.attachment import Attachment
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.services.audit_service import record
from app.services.authorization_service import ensure_project_access, ensure_task_access, get_organization_role
from app.repositories import attachment_repository, project_repository, task_repository
from app.utils.file_validator import validate_upload

router = APIRouter()
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".txt", ".csv", ".doc", ".docx"}


def ensure_can_upload(user: User, organization_id: int) -> None:
    if get_organization_role(user, organization_id) == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot upload files")


@router.post("/projects/{project_id}/attachments")
async def upload_project_attachment(project_id: int, file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_project_access(user, project)
    ensure_can_upload(user, project.organization_id)
    content = await validate_upload(file, allowed_extensions=ALLOWED_EXTENSIONS, max_size_bytes=settings.max_upload_size_bytes)
    root = Path(settings.upload_directory)
    root.mkdir(exist_ok=True, parents=True)
    safe_name = f"{uuid4().hex}{Path(file.filename).suffix.lower()}"
    target = root / str(project_id) / safe_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    attachment = attachment_repository.create(db, filename=file.filename, mime_type=file.content_type or "application/octet-stream", file_size=len(content), storage_path=str(target), uploaded_by=user.id, project_id=project.id, task_id=None)
    record(db, "FILE_UPLOADED", "Attachment", attachment.id, user_id=user.id, organization_id=project.organization_id, metadata={"project_id": project.id, "filename": attachment.filename})
    db.commit()
    return {"id": attachment.id, "filename": attachment.filename, "mime_type": attachment.mime_type, "file_size": attachment.file_size, "project_id": attachment.project_id}


@router.post("/tasks/{task_id}/attachments")
async def upload_task_attachment(task_id: int, file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_task_access(user, task)
    ensure_can_upload(user, task.project.organization_id)
    content = await validate_upload(file, allowed_extensions=ALLOWED_EXTENSIONS, max_size_bytes=settings.max_upload_size_bytes)
    root = Path(settings.upload_directory)
    root.mkdir(exist_ok=True, parents=True)
    safe_name = f"{uuid4().hex}{Path(file.filename).suffix.lower()}"
    target = root / str(task_id) / safe_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    attachment = attachment_repository.create(db, filename=file.filename, mime_type=file.content_type or "application/octet-stream", file_size=len(content), storage_path=str(target), uploaded_by=user.id, project_id=task.project_id, task_id=task.id)
    record(db, "FILE_UPLOADED", "Attachment", attachment.id, user_id=user.id, organization_id=task.project.organization_id, metadata={"task_id": task.id, "filename": attachment.filename})
    db.commit()
    return {"id": attachment.id, "filename": attachment.filename, "mime_type": attachment.mime_type, "file_size": attachment.file_size, "task_id": attachment.task_id}


@router.get("/projects/{project_id}/attachments")
def list_project_attachments(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    ensure_project_access(user, project)
    attachments = attachment_repository.list_for_project(db, project_id)
    return [{"id": a.id, "filename": a.filename, "file_size": a.file_size, "project_id": a.project_id} for a in attachments]


@router.get("/tasks/{task_id}/attachments")
def list_task_attachments(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_repository.get_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    ensure_task_access(user, task)
    attachments = attachment_repository.list_for_task(db, task_id)
    return [{"id": a.id, "filename": a.filename, "file_size": a.file_size, "task_id": a.task_id} for a in attachments]


@router.get("/attachments/{attachment_id}")
def get_attachment(attachment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    attachment = attachment_repository.get_by_id(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    if attachment.project_id is not None:
        project = project_repository.get_by_id(db, attachment.project_id)
        if project:
            ensure_project_access(user, project)
    elif attachment.task_id is not None:
        task = task_repository.get_by_id(db, attachment.task_id)
        if task:
            ensure_task_access(user, task)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment resource not found")
    path = Path(attachment.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file not found")
    return FileResponse(path, media_type=attachment.mime_type, filename=attachment.filename)


@router.delete("/attachments/{attachment_id}")
def delete_attachment(attachment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    attachment = attachment_repository.get_by_id(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    project = project_repository.get_by_id(db, attachment.project_id) if attachment.project_id is not None else None
    task = task_repository.get_by_id(db, attachment.task_id) if attachment.task_id is not None else None
    if project is not None:
        ensure_project_access(user, project)
        organization_id = project.organization_id
    elif task is not None:
        ensure_task_access(user, task)
        organization_id = task.project.organization_id
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment resource not found")
    role = normalize_role_name(user.role.name if user.role else None)
    has_org_manager_role = role == "super_admin" or any(
        membership.organization_id == organization_id
        and membership.is_active
        and normalize_role_name(membership.role) in {"org_admin", "project_manager"}
        for membership in user.organization_memberships
    )
    if attachment.uploaded_by != user.id and not has_org_manager_role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this attachment")
    path = Path(attachment.storage_path)
    if path.exists():
        path.unlink()
    record(db, "FILE_DELETED", "Attachment", attachment.id, user_id=user.id, organization_id=organization_id)
    attachment_repository.delete(db, attachment)
    db.commit()
    return {"message": "Attachment deleted"}
