from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.services.auth_service import create_user


def create_super_admin(client):
    with SessionLocal() as db:
        admin = create_user(
            db,
            name="Platform Super Admin",
            email="platform-admin@example.com",
            password="Secret123!",
            role_name="super_admin",
        )
        db.commit()
        admin_id = admin.id
    login = client.post(
        "/auth/login",
        json={"email": "platform-admin@example.com", "password": "Secret123!"},
    )
    assert login.status_code == 200, login.text
    return admin_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_super_admin_can_create_users_with_supported_roles(client):
    admin_id, headers = create_super_admin(client)
    roles = ["super_admin", "org_admin", "project_manager", "team_member", "viewer"]

    for index, role in enumerate(roles):
        response = client.post(
            "/users",
            json={
                "name": f"Provisioned {role}",
                "email": f"provisioned-{index}@example.com",
                "password": "Secret123!",
                "role": role,
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["role"] == role
        assert "hashed_password" not in response.json()

    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.id == admin_id))
        assert admin is not None and admin.role.name == "super_admin"


def test_non_super_admin_cannot_create_user(client):
    registered = client.post(
        "/auth/register",
        json={
            "name": "Organization Admin",
            "email": "non-super-admin@example.com",
            "password": "Secret123!",
        },
    )
    login = client.post(
        "/auth/login",
        json={"email": "non-super-admin@example.com", "password": "Secret123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/users",
        json={
            "name": "Unauthorized",
            "email": "unauthorized@example.com",
            "password": "Secret123!",
            "role": "viewer",
        },
        headers=headers,
    )

    assert response.status_code == 403


def test_organization_admin_can_create_only_project_managers_and_team_members(client):
    _, super_admin_headers = create_super_admin(client)
    organization_admin = client.post(
        "/users",
        json={
            "name": "Organization Admin",
            "email": "organization-admin@example.com",
            "password": "Secret123!",
            "role": "org_admin",
        },
        headers=super_admin_headers,
    )
    assert organization_admin.status_code == 201, organization_admin.text
    login = client.post(
        "/auth/login",
        json={"email": "organization-admin@example.com", "password": "Secret123!"},
    )
    organization_admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    for role in ("project_manager", "team_member"):
        response = client.post(
            "/users",
            json={
                "name": f"Created {role}",
                "email": f"created-{role}@example.com",
                "password": "Secret123!",
                "role": role,
            },
            headers=organization_admin_headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["role"] == role

    response = client.post(
        "/users",
        json={
            "name": "Viewer",
            "email": "created-viewer@example.com",
            "password": "Secret123!",
            "role": "viewer",
        },
        headers=organization_admin_headers,
    )
    assert response.status_code == 403


def test_super_admin_can_update_user_name_and_email(client):
    _, headers = create_super_admin(client)
    created = client.post(
        "/users",
        json={
            "name": "Original Name",
            "email": "original@example.com",
            "password": "Secret123!",
            "role": "team_member",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]

    updated = client.put(
        f"/users/{user_id}",
        json={"name": "Updated Name", "email": "updated@example.com"},
        headers=headers,
    )

    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["name"] == "Updated Name"
    assert payload["email"] == "updated@example.com"


def test_public_registration_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "allow_public_registration", False)

    response = client.post(
        "/auth/register",
        json={"name": "Self Signup", "email": "self-signup@example.com", "password": "Secret123!"},
    )

    assert response.status_code == 403
