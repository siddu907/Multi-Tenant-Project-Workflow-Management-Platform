from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.user_repository import get_by_email, get_by_id
from app.repositories.refresh_token_repository import get_active_by_token
from app.services.audit_service import record, request_ip
from app.services.auth_service import authenticate_user, create_user, create_refresh_token_record, revoke_user_refresh_tokens, set_password
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RefreshTokenRequest, RegisterRequest

router = APIRouter()


def user_data(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role.name if user.role else "viewer",
        "role_id": user.role_id,
        "is_active": user.is_active,
        "created_at": user.created_at.strftime("%Y-%m-%d %I:%M %p"),
        "updated_at": user.updated_at.strftime("%Y-%m-%d %I:%M %p"),
    }


def token_pair(user: User, db: Session) -> dict:
    role_name = user.role.name if user.role else "viewer"
    access_token = create_token(str(user.id), role_name, timedelta(minutes=settings.access_token_expire_minutes), "access", user.token_version)
    refresh_token = create_token(str(user.id), role_name, timedelta(days=settings.refresh_token_expire_days), "refresh", user.token_version)
    create_refresh_token_record(db, user.id, refresh_token)
    db.commit()
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db), http_request: Request = None):
    if not settings.allow_public_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled; contact a super admin",
        )
    request = request.model_dump()
    email = str(request.get("email", "")).lower().strip()
    password = str(request.get("password") or "")
    name = str(request.get("name") or "User")

    if not email or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email and password are required")
    if get_by_email(db, email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    user = create_user(db, name=name, email=email, password=password, role_name="team_member")
    record(db, "USER_CREATED", "User", user.id, user_id=user.id, metadata={"source": "registration"}, ip_address=request_ip(http_request))
    db.commit()
    return user_data(user)


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db), http_request: Request = None):
    request = request.model_dump()
    email = str(request.get("email", "")).lower().strip()
    password = str(request.get("password") or "")

    user = authenticate_user(db, email, password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    record(db, "LOGIN", "User", user.id, user_id=user.id, metadata={"authentication": "password"}, ip_address=request_ip(http_request))
    payload = token_pair(user, db)
    payload["user"] = user_data(user)
    return payload


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_data(user)


@router.post("/change-password")
def change_password(request: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    request = request.model_dump()
    new_password = str(request.get("new_password") or "")
    if not new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password is required")
    if verify_password(new_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different from the current password")
    set_password(user, new_password)
    revoke_user_refresh_tokens(db, user.id)
    record(db, "PASSWORD_CHANGED", "User", user.id, user_id=user.id)
    db.commit()
    return {"message": "Password changed successfully"}


@router.post("/refresh")
def refresh(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    request = request.model_dump()
    refresh_token_value = request.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token is required")
    try:
        payload = decode_token(refresh_token_value)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc
    user = get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    stored = get_active_by_token(db, refresh_token_value, user.id)
    if stored is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    stored.revoked = True
    return token_pair(user, db)


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    revoke_user_refresh_tokens(db, user.id)
    user.token_version += 1
    record(db, "LOGOUT", "User", user.id, user_id=user.id)
    db.commit()
    return {"message": "Logged out successfully"}