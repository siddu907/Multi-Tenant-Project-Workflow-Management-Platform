from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.notification_service import (
    get_notification,
    list_user_notifications,
    mark_all_user_notifications_read,
    mark_notification_read as set_notification_read,
)

router = APIRouter()


@router.get("/notifications")
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notifications = list_user_notifications(db, user.id)
    return [{"id": n.id, "type": n.type, "message": n.message, "is_read": n.is_read, "created_at": n.created_at.isoformat()} for n in notifications]


@router.put("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notification = get_notification(db, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notification.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to read this notification")
    set_notification_read(db, notification)
    db.commit()
    return {"message": "Notification marked as read"}


@router.put("/notifications/read-all")
def mark_all_notifications_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mark_all_user_notifications_read(db, user.id)
    db.commit()
    return {"message": "All notifications marked as read"}
