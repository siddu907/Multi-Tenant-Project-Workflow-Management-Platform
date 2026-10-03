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


def test_add_and_list_task_dependencies(client):
    _register_user(client, name="Dependency Admin", email="dependency-admin@example.com", role="org_admin")
    auth = _login(client, email="dependency-admin@example.com")

    org_response = client.post(
        "/organizations",
        json={"name": "Dependency Org", "description": "dependency tests"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    org_id = org_response.json()["id"]

    project_response = client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Dependency Project"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    project_id = project_response.json()["id"]

    task_one = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Parent task"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    task_two = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Child task"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )

    dependency_response = client.post(
        f"/api/tasks/{task_two.json()['id']}/dependencies",
        json={"depends_on_task_id": task_one.json()["id"]},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert dependency_response.status_code == 200, dependency_response.text

    list_response = client.get(
        f"/api/tasks/{task_two.json()['id']}/dependencies",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert list_response.status_code == 200, list_response.text
    payload = list_response.json()
    assert payload["task_id"] == task_two.json()["id"]
    assert any(item["depends_on_task_id"] == task_one.json()["id"] for item in payload["dependencies"])


def test_circular_dependency_is_rejected(client):
    _register_user(client, name="Circular Admin", email="circular-admin@example.com", role="org_admin")
    auth = _login(client, email="circular-admin@example.com")

    org_response = client.post(
        "/organizations",
        json={"name": "Circular Org", "description": "cyclic dependency"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    org_id = org_response.json()["id"]

    project_response = client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Circular Project"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    project_id = project_response.json()["id"]

    task_one = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "A"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    ).json()
    task_two = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "B"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    ).json()

    first = client.post(
        f"/api/tasks/{task_two['id']}/dependencies",
        json={"depends_on_task_id": task_one['id']},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/tasks/{task_one['id']}/dependencies",
        json={"depends_on_task_id": task_two['id']},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert second.status_code == 409
    assert "Circular dependency" in second.json()["detail"]


def test_dependent_task_cannot_advance_before_prerequisite_is_done(client):
    _register_user(client, name="Dependency Gate Admin", email="dependency-gate@example.com")
    auth = _login(client, email="dependency-gate@example.com")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    organization = client.post("/organizations", json={"name": "Dependency Gate Org"}, headers=headers)
    project = client.post(
        "/projects",
        json={"organization_id": organization.json()["id"], "name": "Dependency Gate Project"},
        headers=headers,
    )
    prerequisite = client.post(
        "/tasks", json={"project_id": project.json()["id"], "title": "Prerequisite"}, headers=headers
    ).json()
    dependent = client.post(
        "/tasks", json={"project_id": project.json()["id"], "title": "Dependent"}, headers=headers
    ).json()
    dependency = client.post(
        f"/api/tasks/{dependent['id']}/dependencies",
        json={"depends_on_task_id": prerequisite["id"]},
        headers=headers,
    )
    assert dependency.status_code == 200, dependency.text
    assert client.put(f"/tasks/{dependent['id']}/status", json={"status": "todo"}, headers=headers).status_code == 200

    blocked = client.put(
        f"/tasks/{dependent['id']}/status", json={"status": "in_progress"}, headers=headers
    )

    assert blocked.status_code == 409
    assert "dependencies" in blocked.json()["detail"].lower()
