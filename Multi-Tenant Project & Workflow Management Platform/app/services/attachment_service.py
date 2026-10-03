from pathlib import Path

from app.models.attachment import Attachment


def build_attachment_payload(attachment: Attachment):
    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "mime_type": attachment.mime_type,
        "file_size": attachment.file_size,
        "project_id": attachment.project_id,
        "task_id": attachment.task_id,
        "uploaded_by": attachment.uploaded_by,
        "storage_path": attachment.storage_path,
    }


def is_owner_or_admin(user, attachment: Attachment) -> bool:
    if not user:
        return False
    return user.id == attachment.uploaded_by or getattr(user.role, "name", "").lower() in {"super_admin", "org_admin"}


def safe_filename(filename: str) -> str:
    return Path(filename).name
