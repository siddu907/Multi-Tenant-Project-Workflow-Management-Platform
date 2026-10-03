import io

from app.config import settings
from tests.conftest import provision_test_user


def _register_user(client, *, name, email, password="Secret123!", role="org_admin"):
    return provision_test_user(client, name=name, email=email, password=password, role=role)


def _login(client, *, email, password="Secret123!"):
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_upload_accepts_valid_text_file(client):
    admin = _register_user(client, name="File Admin", email="file-admin@example.com", role="org_admin")
    auth = _login(client, email="file-admin@example.com")

    org_response = client.post(
        "/organizations",
        json={"name": "File Org", "description": "file uploads"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    org_id = org_response.json()["id"]

    project_response = client.post(
        "/projects",
        json={"organization_id": org_id, "name": "File Project"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    project_id = project_response.json()["id"]

    response = client.post(
        f"/projects/{project_id}/attachments",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["filename"] == "notes.txt"

    download = client.get(
        f"/attachments/{payload['id']}",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert download.status_code == 200, download.text
    assert download.content == b"hello world"
    assert download.headers["content-type"] == "text/plain; charset=utf-8"
    assert 'attachment; filename="notes.txt"' in download.headers["content-disposition"]


def test_upload_rejects_unsupported_extension(client):
    _register_user(client, name="File Admin 2", email="file-admin-2@example.com", role="org_admin")
    auth = _login(client, email="file-admin-2@example.com")
    org_response = client.post(
        "/organizations",
        json={"name": "Bad File Org", "description": "invalid upload"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    project_response = client.post(
        "/projects",
        json={"organization_id": org_response.json()["id"], "name": "Bad File Project"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )

    response = client.post(
        f"/projects/{project_response.json()['id']}/attachments",
        files={"file": ("malware.exe", b"binary", "application/octet-stream")},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type"


def test_upload_rejects_oversized_file(client):
    _register_user(client, name="File Admin 3", email="file-admin-3@example.com", role="org_admin")
    auth = _login(client, email="file-admin-3@example.com")
    org_response = client.post(
        "/organizations",
        json={"name": "Large File Org", "description": "oversized"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    project_response = client.post(
        "/projects",
        json={"organization_id": org_response.json()["id"], "name": "Large File Project"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )

    response = client.post(
        f"/projects/{project_response.json()['id']}/attachments",
        files={"file": ("large.txt", b"x" * (settings.max_upload_size_bytes + 1), "text/plain")},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "File exceeds maximum allowed size"


def test_upload_rejects_content_that_does_not_match_extension(client):
    _register_user(client, name="File Admin 4", email="file-admin-4@example.com", role="org_admin")
    auth = _login(client, email="file-admin-4@example.com")
    organization = client.post(
        "/organizations", json={"name": "Spoofed File Org"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    project = client.post(
        "/projects", json={"organization_id": organization.json()["id"], "name": "Spoofed File Project"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )

    response = client.post(
        f"/projects/{project.json()['id']}/attachments",
        files={"file": ("fake.pdf", b"not actually a PDF", "application/pdf")},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )

    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]
