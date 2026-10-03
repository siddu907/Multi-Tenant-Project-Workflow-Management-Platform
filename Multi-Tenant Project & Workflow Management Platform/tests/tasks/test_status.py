from tests.conftest import provision_test_user


def _register_and_login(client, *, email, role="org_admin"):
    return provision_test_user(client, name="Status User", email=email, role=role)


def test_valid_status_transition(client):
    auth = _register_and_login(client, email="status-valid@example.com", role="org_admin")
    org_response = client.post(
        "/organizations",
        json={"name": "Status Org", "description": "status tests"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    project_response = client.post(
        "/projects",
        json={"organization_id": org_response.json()["id"], "name": "Status Project"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    task_response = client.post(
        "/tasks",
        json={"project_id": project_response.json()["id"], "title": "Status test"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    task_id = task_response.json()["id"]

    response = client.put(
        f"/tasks/{task_id}/status",
        json={"status": "todo"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "todo"


def test_invalid_status_transition_is_rejected(client):
    auth = _register_and_login(client, email="status-invalid@example.com", role="org_admin")
    org_response = client.post(
        "/organizations",
        json={"name": "Invalid Status Org", "description": "invalid status tests"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    project_response = client.post(
        "/projects",
        json={"organization_id": org_response.json()["id"], "name": "Invalid Status Project"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    task_response = client.post(
        "/tasks",
        json={"project_id": project_response.json()["id"], "title": "Invalid status"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    task_id = task_response.json()["id"]

    response = client.put(
        f"/tasks/{task_id}/status",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 409
    assert "Invalid status transition" in response.json()["detail"]
