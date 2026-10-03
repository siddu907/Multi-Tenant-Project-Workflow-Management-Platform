from datetime import datetime
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.models.task import Task


def create_task_notification(db: Session, user_id: int, task: Task, message: str) -> Notification:
    notification = Notification(user_id=user_id, type="task", message=message, is_read=False)
    db.add(notification)
    db.flush()
    return notification


def send_due_soon_notifications(db: Session, user_id: int, task: Task) -> Notification | None:
    if task.due_date is None:
        return None
    if task.assignee_id != user_id:
        return None
    now = datetime.utcnow().date()
    if task.due_date <= now:
        return create_task_notification(db, user_id, task, f"Task '{task.title}' is due or overdue.")
    return create_task_notification(db, user_id, task, f"Task '{task.title}' is approaching its due date.")
