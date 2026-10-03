from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.notification import Notification


def get_by_id(db: Session, notification_id: int):
    return db.get(Notification, notification_id)


def list_for_user(db: Session, user_id: int):
    return db.scalars(
        select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
    ).all()


def mark_read(db: Session, notification_id: int, user_id: int):
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        return None
    notification.is_read = True
    db.flush()
    return notification


def mark_all_read(db: Session, user_id: int):
    updated = db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read.is_(False)).update({"is_read": True})
    db.flush()
    return updated


def mark_as_read(notification: Notification) -> Notification:
    notification.is_read = True
    return notification


def create(db: Session, user_id: int, notification_type: str, message: str):
    notification = Notification(user_id=user_id, type=notification_type, message=message, is_read=False)
    db.add(notification)
    db.flush()
    return notification
