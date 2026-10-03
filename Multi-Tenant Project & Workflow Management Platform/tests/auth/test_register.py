def _register(client, *, email, password="Secret123!", name="Registered User", **extra):
    response = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password, **extra},
    )
    return response


def test_register_success(client):
    response = _register(client, email="register-success@example.com")
    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "register-success@example.com"
    assert payload["role"] == "team_member"
    assert "access_token" not in payload
    assert "refresh_token" not in payload


def test_register_duplicate_email_is_rejected(client):
    first = _register(client, email="duplicate@example.com")
    assert first.status_code == 201

    second = _register(client, email="duplicate@example.com")
    assert second.status_code == 409
    assert second.json()["detail"] == "Email already exists"


def test_register_rejects_role_input(client):
    response = _register(client, email="role-input@example.com", role="org_admin")
    assert response.status_code == 422


def test_register_invalid_password_returns_validation_envelope(client):
    response = _register(client, email="weak-password@example.com", password="weak")

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "HTTP_422"
