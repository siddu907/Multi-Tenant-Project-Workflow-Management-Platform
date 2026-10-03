import json

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.repositories import notification_repository
from app.websocket.manager import manager


def list_user_notifications(db: Session, user_id: int):
    return notification_repository.list_for_user(db, user_id)


def get_notification(db: Session, notification_id: int) -> Notification | None:
    return notification_repository.get_by_id(db, notification_id)


def mark_notification_read(db: Session, notification: Notification) -> Notification:
    return notification_repository.mark_as_read(notification)


def mark_all_user_notifications_read(db: Session, user_id: int) -> int:
    return notification_repository.mark_all_read(db, user_id)


def create_notification(db: Session, *, user_id: int, notification_type: str, message: str):
    notification = Notification(user_id=user_id, type=notification_type, message=message, is_read=False)
    db.add(notification)
    db.flush()
    return notification


def notify_mention(db: Session, *, recipient_id: int, actor_name: str, task_id: int):
    return create_notification(
        db,
        user_id=recipient_id,
        notification_type="mention",
        message=f"{actor_name} mentioned you on task #{task_id}",
    )


def create_and_push_notification(
    db: Session,
    background_tasks: BackgroundTasks,
    *,
    user_id: int,
    notification_type: str,
    message: str,
) -> Notification:
    notification = create_notification(
        db,
        user_id=user_id,
        notification_type=notification_type,
        message=message,
    )
    background_tasks.add_task(
        manager.send_personal_message,
        json.dumps(
            {
                "id": notification.id,
                "type": notification.type,
                "message": notification.message,
                "created_at": notification.created_at.isoformat() if notification.created_at else None,
            }
        ),
        user_id,
    )
    return notification
