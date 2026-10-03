from tests.conftest import provision_test_user


def _register_and_login(client, *, email, name="Project User", role="org_admin"):
    return provision_test_user(client, name=name, email=email, role=role)


def test_create_and_get_project(client):
    auth = _register_and_login(client, email="project-create@example.com")
    org_response = client.post(
        "/organizations",
        json={"name": "Project Org", "description": "project tests"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    org_id = org_response.json()["id"]

    create_response = client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Project A", "description": "Initial"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert create_response.status_code == 200
    project_id = create_response.json()["id"]

    get_response = client.get(
        f"/projects/{project_id}",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Project A"


def test_update_project(client):
    auth = _register_and_login(client, email="project-update@example.com")
    org_response = client.post(
        "/organizations",
        json={"name": "Project Update Org", "description": "update tests"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    project_response = client.post(
        "/projects",
        json={"organization_id": org_response.json()["id"], "name": "Old Project"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    project_id = project_response.json()["id"]

    response = client.put(
        f"/projects/{project_id}",
        json={"name": "Updated Project", "description": "new description"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Project"


def test_project_status_transition_rules_are_enforced(client):
    auth = _register_and_login(client, email="project-status@example.com")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    organization = client.post("/organizations", json={"name": "Project Status Org"}, headers=headers)
    project = client.post(
        "/projects",
        json={"organization_id": organization.json()["id"], "name": "Project Status"},
        headers=headers,
    )

    invalid = client.put(f"/projects/{project.json()['id']}", json={"status": "invented"}, headers=headers)
    assert invalid.status_code == 400

    direct_completion = client.put(
        f"/projects/{project.json()['id']}", json={"status": "completed"}, headers=headers
    )
    assert direct_completion.status_code == 409

    active = client.put(f"/projects/{project.json()['id']}", json={"status": "active"}, headers=headers)
    assert active.status_code == 200

    completed = client.put(
        f"/projects/{project.json()['id']}", json={"status": "completed"}, headers=headers
    )
    assert completed.status_code == 200

    reopen = client.put(f"/projects/{project.json()['id']}", json={"status": "active"}, headers=headers)
    assert reopen.status_code == 409


def test_project_delete_cascades_project_data(client):
    auth = _register_and_login(client, email="project-delete@example.com")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    organization = client.post("/organizations", json={"name": "Project Delete Org"}, headers=headers)
    project = client.post(
        "/projects", json={"organization_id": organization.json()["id"], "name": "Deletable Project"}, headers=headers
    )
    task = client.post(
        "/tasks", json={"project_id": project.json()["id"], "title": "Cascaded Task"}, headers=headers
    )

    deleted = client.delete(f"/projects/{project.json()['id']}", headers=headers)

    assert deleted.status_code == 200, deleted.text
    assert client.get(f"/projects/{project.json()['id']}", headers=headers).status_code == 404
    assert client.get(f"/tasks/{task.json()['id']}", headers=headers).status_code == 404
