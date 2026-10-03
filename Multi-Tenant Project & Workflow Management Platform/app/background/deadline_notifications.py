from datetime import date, datetime, time, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.notification import Notification
from app.models.task import Task
from app.websocket.manager import manager


def create_deadline_notifications(db: Session, today: date | None = None) -> int:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        lock_acquired = db.scalar(text("SELECT pg_try_advisory_xact_lock(:lock_id)"), {"lock_id": 72390438214051})
        if not lock_acquired:
            db.rollback()
            return 0
    today = today or date.today()
    tomorrow = today + timedelta(days=1)
    day_start = datetime.combine(today, time.min)
    tasks = db.scalars(
        select(Task).where(
            Task.assignee_id.is_not(None),
            Task.due_date.is_not(None),
            Task.due_date <= tomorrow,
            Task.status.notin_(["done", "cancelled"]),
        )
    ).all()
    created = 0
    pending_pushes: list[tuple[Notification, int]] = []
    for task in tasks:
        notification_type = "task_overdue" if task.due_date < today else "task_due_soon"
        message = (
            f"Task '{task.title}' is overdue."
            if notification_type == "task_overdue"
            else f"Task '{task.title}' is due soon."
        )
        exists = db.scalar(
            select(Notification.id).where(
                Notification.user_id == task.assignee_id,
                Notification.type == notification_type,
                Notification.message == message,
                Notification.created_at >= day_start,
            )
        )
        if exists is None:
            notification = Notification(
                user_id=task.assignee_id,
                type=notification_type,
                message=message,
                is_read=False,
            )
            db.add(notification)
            db.flush()
            pending_pushes.append((notification, task.assignee_id))
            created += 1
    db.commit()
    for notification, user_id in pending_pushes:
        manager.push_notification_from_background(notification, user_id)
    return created


def main() -> None:
    with SessionLocal() as db:
        count = create_deadline_notifications(db)
    print(f"Created {count} task deadline notifications")


if __name__ == "__main__":
    main()
