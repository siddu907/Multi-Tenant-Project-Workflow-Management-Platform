from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.refresh_token import RefreshToken

def get_active_for_user(db: Session, user_id: int):
    return db.scalars(select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))).all()


def get_active_by_token(db: Session, token_value: str, user_id: int):
    return db.scalar(
        select(RefreshToken).where(
            RefreshToken.token == token_value,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
        )
    )


def revoke_all_for_user(db: Session, user_id: int):
    updated = db.query(RefreshToken).filter(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)).update({"revoked": True})
    db.flush()
    return updated


def revoke_every_for_user(db: Session, user_id: int):
    updated = db.query(RefreshToken).filter(RefreshToken.user_id == user_id).update({"revoked": True})
    db.flush()
    return updated


def revoke_by_token(db: Session, token_value: str):
    token = db.scalar(select(RefreshToken).where(RefreshToken.token == token_value))
    if token is not None:
        token.revoked = True
        db.flush()
    return token
