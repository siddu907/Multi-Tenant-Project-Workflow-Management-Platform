import uuid
from datetime import timedelta
from sqlalchemy import select

from app.core.security import create_token
from app.database import SessionLocal
from app.models.user import User
from tests.conftest import provision_test_user


def _register_and_login(client, *, email=None, password="Secret123!", name="Test User", role="org_admin"):
    email = email or f"{uuid.uuid4().hex[:8]}@example.com"
    return provision_test_user(client, name=name, email=email, password=password, role=role)


def test_login_success(client):
    payload = _register_and_login(client, email="login-success@example.com")
    assert payload["user"]["email"] == "login-success@example.com"
    assert "access_token" in payload
    assert payload["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    response = client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "HTTP_401"
    assert response.json()["error"]["message"] == "Invalid credentials"
    assert response.json()["detail"] == "Invalid credentials"


def test_inactive_user_login_is_blocked(client):
    email = "inactive@example.com"
    registered = provision_test_user(client, name="Inactive User", email=email, role="org_admin")
    user_id = registered["user"]["id"]
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.id == user_id))
        assert user is not None
        user.is_active = False
        db.commit()
    finally:
        db.close()

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": "Secret123!"},
    )
    assert login_response.status_code == 401
    assert login_response.json()["detail"] == "Inactive user"



def test_me_endpoint_requires_authentication(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_expired_access_token_is_rejected(client):
    expired = create_token("1", "org_admin", timedelta(seconds=-1), "access")
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_logout_revokes_access_and_refresh_tokens(client):
    payload = _register_and_login(client, email="logout@example.com")
    headers = {"Authorization": f"Bearer {payload['access_token']}"}

    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 200

    access_response = client.get("/auth/me", headers=headers)
    assert access_response.status_code == 401

    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert refresh_response.status_code == 401
