from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.core.permissions import normalize_role_name
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.audit_service import record
from app.schemas.auth import UserCreateRequest
from app.schemas.user import UserUpdateRequest
from app.services.auth_service import DEFAULT_ROLES, create_user
from app.repositories import user_repository

router = APIRouter()


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user_account(request: UserCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    creator_role = normalize_role_name(user.role.name if user.role else None)
    if creator_role not in {"super_admin", "org_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins and organization admins can create user accounts")
    data = request.model_dump()
    role_name = normalize_role_name(data.get("role"))
    if role_name not in DEFAULT_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    if creator_role == "org_admin" and role_name not in {"project_manager", "team_member"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admins can create only project managers and team members")
    new_user = create_user(
        db,
        name=data["name"],
        email=str(data["email"]).lower(),
        password=data["password"],
        role_name=role_name,
    )
    record(db, "USER_CREATED", "User", new_user.id, user_id=user.id, metadata={"source": creator_role, "role": role_name})
    db.commit()
    return {
        "id": new_user.id,
        "name": new_user.name,
        "email": new_user.email,
        "role": new_user.role.name,
        "is_active": new_user.is_active,
    }


@router.get("/users")
def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = normalize_role_name(user.role.name if user.role else None)
    if role in {"super_admin", "org_admin"}:
        users = user_repository.list_all(db)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin permissions required")
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role.name if u.role else "viewer", "is_active": u.is_active} for u in users]


@router.get("/users/{user_id}")
def get_user(user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = normalize_role_name(user.role.name if user.role else None)
    if role == "super_admin":
        target = user_repository.get_by_id(db, user_id)
    else:
        organization_ids = [
            membership.organization_id
            for membership in user.organization_memberships
            if membership.is_active and normalize_role_name(membership.role) in {"org_admin", "admin"}
        ]
        if not organization_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin permissions required")
        target = user_repository.get_for_organizations(db, user_id, organization_ids)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"id": target.id, "name": target.name, "email": target.email, "role": target.role.name if target.role else "viewer", "is_active": target.is_active}


@router.put("/users/{user_id}")
def update_user(user_id: int, request: UserUpdateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if normalize_role_name(user.role.name if user.role else None) != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can update user accounts")

    target = user_repository.get_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updated_fields = []

    if request.name is not None:
        name = request.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name cannot be empty")
        target.name = name
        updated_fields.append("name")

    if request.email is not None:
        email = str(request.email).lower()
        existing = user_repository.get_by_email(db, email)
        if existing and existing.id != target.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        target.email = email
        updated_fields.append("email")

    if not updated_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field must be provided for update")

    record(db, "USER_UPDATED", "User", target.id, user_id=user.id, metadata={"fields": updated_fields})
    db.commit()
    return {"id": target.id, "name": target.name, "email": target.email, "role": target.role.name if target.role else "viewer", "is_active": target.is_active}


@router.put("/users/{user_id}/activate")
def activate_user(user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if normalize_role_name(user.role.name if user.role else None) != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can activate global user accounts")
    target = user_repository.get_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    target.is_active = True
    record(db, "USER_ACTIVATED", "User", target.id, user_id=user.id)
    db.commit()
    return {"message": "User activated"}


@router.put("/users/{user_id}/deactivate")
def deactivate_user(user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if normalize_role_name(user.role.name if user.role else None) != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can deactivate global user accounts")
    target = user_repository.get_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    target.is_active = False
    record(db, "USER_DEACTIVATED", "User", target.id, user_id=user.id)
    db.commit()
    return {"message": "User deactivated"}
