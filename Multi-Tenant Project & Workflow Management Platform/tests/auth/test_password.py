from tests.conftest import provision_test_user


def _register_and_login(client, *, email, password="Secret123!", name="Password User", role="org_admin"):
    return provision_test_user(client, name=name, email=email, password=password, role=role)


def test_change_password_success(client):
    auth = _register_and_login(client, email="password-change@example.com")
    response = client.post(
        "/auth/change-password",
        json={"new_password": "NewSecret456!"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password changed successfully"

    next_login = client.post(
        "/auth/login",
        json={"email": "password-change@example.com", "password": "NewSecret456!"},
    )
    assert next_login.status_code == 200


def test_change_password_rejects_same_password(client):
    auth = _register_and_login(client, email="same-password@example.com")
    response = client.post(
        "/auth/change-password",
        json={"new_password": "Secret123!"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "New password must be different from the current password"
