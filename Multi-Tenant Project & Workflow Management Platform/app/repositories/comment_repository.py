from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.comment import Comment


def get_by_id(db: Session, comment_id: int):
    return db.get(Comment, comment_id)


def list_for_task(db: Session, task_id: int):
    return db.scalars(select(Comment).where(Comment.task_id == task_id).order_by(Comment.created_at.asc())).all()


def list_for_project(db: Session, project_id: int):
    return db.scalars(select(Comment).where(Comment.project_id == project_id).order_by(Comment.created_at.asc())).all()


def create(db: Session, *, content: str, user_id: int, task_id: int | None = None, project_id: int | None = None):
    comment = Comment(content=content, user_id=user_id, task_id=task_id, project_id=project_id)
    db.add(comment)
    db.flush()
    return comment


def delete(db: Session, comment: Comment):
    db.delete(comment)
