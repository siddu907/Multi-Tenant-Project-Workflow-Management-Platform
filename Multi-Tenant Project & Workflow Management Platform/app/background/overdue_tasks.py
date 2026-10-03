from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.models.task import Task


def find_overdue_tasks(db: Session):
    today = date.today()
    return db.scalars(select(Task).where(Task.due_date != None, Task.due_date < today)).all()


def create_overdue_notifications(db: Session, user_id: int, overdue_tasks: list[Task]) -> list[Notification]:
    notifications = []
    for task in overdue_tasks:
        if task.assignee_id != user_id:
            continue
        notification = Notification(
            user_id=user_id,
            type="overdue",
            message=f"Task '{task.title}' is overdue.",
            is_read=False,
        )
        db.add(notification)
        notifications.append(notification)
    db.flush()
    return notifications
