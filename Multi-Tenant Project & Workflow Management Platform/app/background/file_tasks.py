from pathlib import Path
from typing import Iterable
from sqlalchemy.orm import Session
from app.models.attachment import Attachment


def cleanup_orphaned_files(db: Session, upload_root: str | Path, allowed_extensions: Iterable[str]) -> list[str]:
    root = Path(upload_root)
    if not root.exists():
        return []
    existing_paths = {str(item.resolve()) for item in root.rglob('*') if item.is_file()}
    stored_paths = {str(Path(att.storage_path).resolve()) for att in db.query(Attachment).all() if att.storage_path}
    orphans = sorted(existing_paths - stored_paths)
    for file_path in orphans:
        path = Path(file_path)
        if path.exists():
            path.unlink(missing_ok=True)
    return orphans


def scan_and_validate_uploads(db: Session, upload_root: str | Path, allowed_extensions: Iterable[str]) -> list[Attachment]:
    root = Path(upload_root)
    if not root.exists():
        return []
    valid_exts = {ext.lower() for ext in allowed_extensions}
    attachments = []
    for file_path in root.rglob('*'):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in valid_exts:
            continue
        attachment = db.query(Attachment).filter(Attachment.storage_path == str(file_path)).first()
        if attachment is not None:
            attachments.append(attachment)
    return attachments
