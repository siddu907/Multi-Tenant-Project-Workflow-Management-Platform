from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.attachment import Attachment

def get_by_id(db: Session, attachment_id: int):
    return db.get(Attachment, attachment_id)


def list_for_project(db: Session, project_id: int):
    return db.scalars(select(Attachment).where(Attachment.project_id == project_id)).all()


def list_for_task(db: Session, task_id: int):
    return db.scalars(select(Attachment).where(Attachment.task_id == task_id)).all()


def create(db: Session, **kwargs):
    attachment = Attachment(**kwargs)
    db.add(attachment)
    db.flush()
    return attachment


def delete(db: Session, attachment: Attachment):
    db.delete(attachment)
