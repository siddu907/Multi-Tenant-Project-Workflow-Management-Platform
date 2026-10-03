from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.core.permissions import normalize_role_name
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.audit_service import record
from app.services.authorization_service import ensure_organization_access, ensure_organization_admin
from app.schemas.organization import OrganizationCreate, OrganizationMemberCreate, OrganizationMemberRoleUpdate, OrganizationUpdate
from app.repositories import organization_repository, user_repository
from app.services import organization_service

router = APIRouter(prefix="/organizations")


ensure_org_admin = ensure_organization_admin


ensure_org_access = ensure_organization_access


def membership_payload(member: OrganizationMember) -> dict:
    return {
        "id": member.id,
        "organization_id": member.organization_id,
        "user_id": member.user_id,
        "role": member.role,
        "is_active": member.is_active,
        "joined_at": member.joined_at.isoformat(),
    }


@router.post("")
def create_organization(request: OrganizationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role.name.lower() not in {"super_admin", "org_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can create organizations")

    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization name is required")
    is_super_admin = user.role.name.lower() == "super_admin"
    org = organization_service.create_organization(
        db,
        name=name,
        description=request.description,
        owner_id=None if is_super_admin else user.id,
    )
    member = None if is_super_admin else organization_repository.get_member(db, org.id, user.id)
    db.flush()
    if member is not None:
        record(db, "MEMBER_ADDED", "OrganizationMember", member.id, user_id=user.id, organization_id=org.id, metadata={"member_user_id": user.id})
    record(db, "ORGANIZATION_CREATED", "Organization", org.id, user_id=user.id, organization_id=org.id)
    db.commit()
    return {"id": org.id, "name": org.name, "description": org.description}


@router.get("")
def list_organizations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role.name.lower() == "super_admin":
        orgs = organization_repository.list_all(db)
    else:
        orgs = organization_repository.list_for_user(db, user.id)
    return [{"id": org.id, "name": org.name, "description": org.description} for org in orgs]


@router.get("/{organization_id}")
def get_organization(organization_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = organization_repository.get_by_id(db, organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ensure_org_access(user, org.id)
    return {"id": org.id, "name": org.name, "description": org.description}


@router.put("/{organization_id}")
def update_organization(organization_id: int, request: OrganizationUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = organization_repository.get_by_id(db, organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ensure_org_admin(user, organization_id)
    changes = request.model_dump(exclude_unset=True)
    organization_service.update_organization(db, org, changes)
    record(db, "ORGANIZATION_UPDATED", "Organization", org.id, user_id=user.id, organization_id=org.id, metadata={"fields": sorted(changes.keys())})
    db.commit()
    return {"id": org.id, "name": org.name, "description": org.description}


@router.delete("/{organization_id}")
def delete_organization(organization_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = organization_repository.get_by_id(db, organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ensure_org_admin(user, organization_id)
    record(db, "ORGANIZATION_DELETED", "Organization", org.id, user_id=user.id, organization_id=org.id)
    organization_service.delete_organization(db, org)
    db.commit()
    return {"message": "Organization deleted"}


@router.get("/{organization_id}/members")
def list_members(organization_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = organization_repository.get_by_id(db, organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ensure_org_access(user, org.id)
    members = organization_repository.get_members(db, organization_id)
    return [membership_payload(member) for member in members]


@router.post("/{organization_id}/members")
def add_member(organization_id: int, request: OrganizationMemberCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if organization_repository.get_by_id(db, organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ensure_org_admin(user, organization_id)
    target_user_id = request.user_id
    target_user = user_repository.get_by_id(db, target_user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not target_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive users cannot be added to an organization")

    role = normalize_role_name(getattr(target_user.role, "name", "team_member"))
    if role not in {"super_admin", "org_admin", "project_manager", "team_member", "viewer"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user role for organization membership")

    existing = organization_repository.get_member(db, organization_id, target_user_id)
    if existing and existing.is_active:
        if existing.role != role:
            organization_service.update_member_role(existing, role)
            record(db, "MEMBER_ROLE_CHANGED", "OrganizationMember", existing.id, user_id=user.id, organization_id=organization_id, metadata={"member_user_id": target_user_id, "from": existing.role, "to": role})
            db.commit()
        return membership_payload(existing)
    if existing:
        organization_service.update_member_role(existing, role)
        organization_service.set_member_active(existing, True)
        record(db, "MEMBER_ACTIVATED", "OrganizationMember", existing.id, user_id=user.id, organization_id=organization_id, metadata={"member_user_id": target_user_id, "role": role})
        db.commit()
        return membership_payload(existing)

    member = organization_service.create_member(db, organization_id=organization_id, user_id=target_user_id, role=role)
    record(db, "MEMBER_ADDED", "OrganizationMember", member.id, user_id=user.id, organization_id=organization_id, metadata={"member_user_id": target_user_id, "role": role})
    db.commit()
    return membership_payload(member)


@router.put("/{organization_id}/members/{user_id}/role")
def update_member_role(organization_id: int, user_id: int, request: OrganizationMemberRoleUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if organization_repository.get_by_id(db, organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ensure_org_admin(user, organization_id)
    member = organization_repository.get_member(db, organization_id, user_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    new_role = request.role.strip().lower()
    if new_role not in {"org_admin", "admin", "project_manager", "team_member", "viewer"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization member role")
    old_role = member.role
    organization_service.update_member_role(member, new_role)
    record(db, "MEMBER_ROLE_CHANGED", "OrganizationMember", member.id, user_id=user.id, organization_id=organization_id, metadata={"member_user_id": user_id, "from": old_role, "to": new_role})
    db.commit()
    return membership_payload(member)


@router.put("/{organization_id}/members/{user_id}/activate")
def activate_member(organization_id: int, user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if organization_repository.get_by_id(db, organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ensure_org_admin(user, organization_id)
    member = organization_repository.get_member(db, organization_id, user_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    record(db, "MEMBER_ACTIVATED", "OrganizationMember", member.id, user_id=user.id, organization_id=organization_id, metadata={"member_user_id": user_id})
    organization_service.set_member_active(member, True)
    db.commit()
    return {"message": "Member activated"}


@router.put("/{organization_id}/members/{user_id}/deactivate")
def deactivate_member(organization_id: int, user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if organization_repository.get_by_id(db, organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ensure_org_admin(user, organization_id)
    member = organization_repository.get_member(db, organization_id, user_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    record(db, "MEMBER_DEACTIVATED", "OrganizationMember", member.id, user_id=user.id, organization_id=organization_id, metadata={"member_user_id": user_id})
    organization_service.set_member_active(member, False)
    db.commit()
    return {"message": "Member deactivated"}


@router.delete("/{organization_id}/members/{user_id}")
def remove_member(organization_id: int, user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_org_admin(user, organization_id)
    member = organization_repository.get_member(db, organization_id, user_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    record(db, "MEMBER_REMOVED", "OrganizationMember", member.id, user_id=user.id, organization_id=organization_id, metadata={"member_user_id": user_id})
    organization_service.remove_member(db, member)
    db.commit()
    return {"message": "Member removed"}
