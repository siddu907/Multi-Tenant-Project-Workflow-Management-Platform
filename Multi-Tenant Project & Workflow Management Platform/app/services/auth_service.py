from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.permissions import normalize_role_name
from app.core.security import hash_password, verify_password
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.user import User
from app.repositories.user_repository import get_by_email, get_role_by_name
from app.repositories.refresh_token_repository import revoke_every_for_user

DEFAULT_ROLES = ["super_admin", "org_admin", "project_manager", "team_member", "viewer"]


def ensure_default_roles(db: Session) -> None:
    for role_name in DEFAULT_ROLES:
        if get_role_by_name(db, role_name) is None:
            db.add(Role(name=role_name))
    db.flush()


def authenticate_user(db: Session, email: str, password: str):
    user = get_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user


def create_user(db: Session, name: str, email: str, password: str, role_name: str = "org_admin") -> User:
    ensure_default_roles(db)
    existing = get_by_email(db, email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    role_name = normalize_role_name(role_name)
    if role_name not in DEFAULT_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    role = get_role_by_name(db, role_name)
    if role is None:
        role = Role(name=role_name)
        db.add(role)
        db.flush()

    user = User(name=name, email=email.lower(), hashed_password=hash_password(password), role_id=role.id, is_active=True)
    db.add(user)
    db.flush()
    return user


def set_password(user: User, new_password: str) -> None:
    user.hashed_password = hash_password(new_password)


def create_refresh_token_record(db: Session, user_id: int, token: str) -> RefreshToken:
    record = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(record)
    return record


def revoke_user_refresh_tokens(db: Session, user_id: int) -> int:
    return revoke_every_for_user(db, user_id)
