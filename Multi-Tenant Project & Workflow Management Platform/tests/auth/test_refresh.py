from datetime import timedelta

from app.core.security import create_token
from tests.conftest import provision_test_user


def test_refresh_token_returns_new_pair(client):
    auth = provision_test_user(client, name="Refresh User", email="refresh-user@example.com", role="org_admin")
    refresh_token = auth["refresh_token"]

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["token_type"] == "bearer"


def test_refresh_token_rejected_if_invalid(client):
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "not-a-valid-token"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


def test_expired_refresh_token_is_rejected(client):
    expired = create_token("1", "org_admin", timedelta(seconds=-1), "refresh")
    response = client.post("/auth/refresh", json={"refresh_token": expired})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"
