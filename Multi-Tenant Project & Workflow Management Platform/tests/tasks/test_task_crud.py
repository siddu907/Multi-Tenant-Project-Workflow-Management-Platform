import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.audit_log import AuditLog
from tests.conftest import provision_test_user


def _register_and_login(client, *, email, role="org_admin"):
    return provision_test_user(client, name="Task User", email=email, role=role)


def test_create_and_list_tasks(client):
    auth = _register_and_login(client, email="task-crud@example.com", role="org_admin")
    org_response = client.post(
        "/organizations",
        json={"name": "Task CRUD Org", "description": "task CRUD"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    org_id = org_response.json()["id"]
    project_response = client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Task CRUD Project"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    project_id = project_response.json()["id"]

    create_response = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Task CRUD Example"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["id"]
    db = SessionLocal()
    try:
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "TASK_CREATED",
                AuditLog.entity_id == task_id,
            )
        )
        assert audit is not None
        assert audit.organization_id == org_id
    finally:
        db.close()

    list_response = client.get(
        "/tasks",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert list_response.status_code == 200
    assert any(task["title"] == "Task CRUD Example" for task in list_response.json()["items"])


@pytest.mark.parametrize(
    ("global_role", "organization_role"),
    [("project_manager", "project_manager"), ("team_member", "project_manager")],
)
def test_project_manager_sees_and_opens_tasks_in_their_project(client, global_role, organization_role):
    admin = _register_and_login(client, email=f"task-manager-admin-{global_role}@example.com", role="org_admin")
    manager = _register_and_login(client, email=f"task-manager-{global_role}@example.com", role=global_role)
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
    manager_headers = {"Authorization": f"Bearer {manager['access_token']}"}

    organization = client.post("/organizations", json={"name": "Manager Visibility Org"}, headers=admin_headers)
    organization_id = organization.json()["id"]
    client.post(
        f"/organizations/{organization_id}/members",
        json={"user_id": manager["user"]["id"]},
        headers=admin_headers,
    )
    role_response = client.put(
        f"/organizations/{organization_id}/members/{manager['user']['id']}/role",
        json={"role": organization_role},
        headers=admin_headers,
    )
    assert role_response.status_code == 200, role_response.text

    project = client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "Manager Visibility Project"},
        headers=admin_headers,
    )
    project_id = project.json()["id"]
    membership = client.post(
        f"/projects/{project_id}/members",
        json={"user_id": manager["user"]["id"]},
        headers=admin_headers,
    )
    assert membership.status_code == 200, membership.text

    task = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Unassigned manager task"},
        headers=admin_headers,
    )
    assert task.status_code == 200, task.text
    task_id = task.json()["id"]

    task_list = client.get("/tasks", headers=manager_headers)
    assert task_list.status_code == 200, task_list.text
    assert any(item["id"] == task_id for item in task_list.json()["items"])

    task_detail = client.get(f"/tasks/{task_id}", headers=manager_headers)
    assert task_detail.status_code == 200, task_detail.text

    if organization_role == "project_manager":
        status_response = client.put(
            f"/tasks/{task_id}/status",
            json={"status": "todo"},
            headers=manager_headers,
        )
        assert status_response.status_code == 200, status_response.text

        update_response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated by organization manager", "priority": "high"},
            headers=manager_headers,
        )
        assert update_response.status_code == 200, update_response.text
        assert update_response.json()["priority"] == "high"


def test_organization_viewer_role_limits_global_project_manager(client):
    admin = _register_and_login(client, email="viewer-scope-admin@example.com", role="org_admin")
    manager = _register_and_login(client, email="viewer-scope-manager@example.com", role="project_manager")
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
    manager_headers = {"Authorization": f"Bearer {manager['access_token']}"}

    organization = client.post("/organizations", json={"name": "Viewer Scope Org"}, headers=admin_headers)
    organization_id = organization.json()["id"]
    client.post(
        f"/organizations/{organization_id}/members",
        json={"user_id": manager["user"]["id"]},
        headers=admin_headers,
    )
    role_response = client.put(
        f"/organizations/{organization_id}/members/{manager['user']['id']}/role",
        json={"role": "viewer"},
        headers=admin_headers,
    )
    assert role_response.status_code == 200, role_response.text

    project = client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "Viewer Scope Project"},
        headers=admin_headers,
    )
    project_id = project.json()["id"]
    membership = client.post(
        f"/projects/{project_id}/members",
        json={"user_id": manager["user"]["id"]},
        headers=admin_headers,
    )
    assert membership.status_code == 200, membership.text
    task = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Viewer scope task"},
        headers=admin_headers,
    )
    task_id = task.json()["id"]

    listed = client.get("/tasks", headers=manager_headers)
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == task_id for item in listed.json()["items"])
    assert client.get(f"/tasks/{task_id}", headers=manager_headers).status_code == 200
    assert client.put(
        f"/tasks/{task_id}/status",
        json={"status": "todo"},
        headers=manager_headers,
    ).status_code == 403
    assert client.put(
        f"/tasks/{task_id}",
        json={"title": "Viewer cannot edit"},
        headers=manager_headers,
    ).status_code == 403


def test_update_task(client):
    auth = _register_and_login(client, email="task-update@example.com", role="org_admin")
    org_response = client.post(
        "/organizations",
        json={"name": "Update Task Org", "description": "update task"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    project_response = client.post(
        "/projects",
        json={"organization_id": org_response.json()["id"], "name": "Update Task Project"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    task_response = client.post(
        "/tasks",
        json={"project_id": project_response.json()["id"], "title": "Before update"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    task_id = task_response.json()["id"]

    response = client.put(
        f"/tasks/{task_id}",
        json={"title": "After update", "priority": "high"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "After update"
    assert payload["priority"] == "high"


def test_task_pagination_reports_total_matching_items(client):
    auth = _register_and_login(client, email="task-pagination@example.com", role="org_admin")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    organization = client.post("/organizations", json={"name": "Pagination Org"}, headers=headers)
    project = client.post(
        "/projects",
        json={"organization_id": organization.json()["id"], "name": "Pagination Project"},
        headers=headers,
    )

    for title in ("Page task one", "Page task two", "Page task three"):
        response = client.post(
            "/tasks",
            json={"project_id": project.json()["id"], "title": title},
            headers=headers,
        )
        assert response.status_code == 200, response.text

    response = client.get("/tasks?page=1&page_size=2", headers=headers)

    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 2
    assert response.json()["total"] == 3


def test_task_filters_and_sorting_apply_before_pagination(client):
    auth = _register_and_login(client, email="task-filtering@example.com", role="org_admin")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    organization = client.post("/organizations", json={"name": "Filtering Org"}, headers=headers)
    project = client.post(
        "/projects",
        json={"organization_id": organization.json()["id"], "name": "Filtering Project"},
        headers=headers,
    )

    for title, priority, due_date in (
        ("Beta payment", "high", "2030-01-02"),
        ("Alpha payment", "high", "2030-01-01"),
        ("Unrelated", "low", "2030-01-01"),
    ):
        response = client.post(
            "/tasks",
            json={"project_id": project.json()["id"], "title": title, "priority": priority, "due_date": due_date},
            headers=headers,
        )
        assert response.status_code == 200, response.text

    response = client.get(
        "/tasks?priority=high&due_date_from=2030-01-01&search=payment&sort_by=title&sort_order=asc&page_size=1",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2
    assert response.json()["items"][0]["title"] == "Alpha payment"


def test_task_list_rejects_invalid_pagination(client):
    auth = _register_and_login(client, email="task-invalid-pagination@example.com", role="org_admin")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    response = client.get(
        "/tasks?page=0&page_size=0",
        headers=headers,
    )
    assert response.status_code == 422

    invalid_sort = client.get("/tasks?sort_by=not_a_task_field", headers=headers)
    assert invalid_sort.status_code == 422
