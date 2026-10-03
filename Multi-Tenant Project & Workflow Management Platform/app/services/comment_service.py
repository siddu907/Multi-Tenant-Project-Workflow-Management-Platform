import re

from sqlalchemy.orm import Session

from app.models.comment import Comment
from app.repositories import comment_repository

MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_.-]+)")


def extract_mentions(message: str):
    return MENTION_PATTERN.findall(message or "")


def create_comment(db: Session, *, content: str, user_id: int, task_id: int | None = None, project_id: int | None = None):
    return comment_repository.create(
        db,
        content=content,
        user_id=user_id,
        task_id=task_id,
        project_id=project_id,
    )


def update_comment(comment: Comment, content: str) -> Comment:
    comment.content = content
    return comment


def delete_comment(db: Session, comment: Comment) -> None:
    comment_repository.delete(db, comment)
