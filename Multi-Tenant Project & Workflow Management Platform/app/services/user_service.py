from sqlalchemy.orm import Session

from app.models.user import User


def set_active_status(user: User, is_active: bool) -> User:
    user.is_active = is_active
    return user


def get_user_summary(user: User):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role.name if getattr(user, "role", None) else "viewer",
        "is_active": user.is_active,
    }


def list_active_users(db: Session, *, role_name: str | None = None):
    query = db.query(User).filter(User.is_active.is_(True))
    if role_name is not None:
        query = query.join(User.role).filter(User.role.has(name=role_name))
    return query.all()
