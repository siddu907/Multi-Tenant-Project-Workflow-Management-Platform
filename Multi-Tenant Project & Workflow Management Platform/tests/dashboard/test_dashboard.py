import uuid

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


def test_organization_dashboard_contains_project_and_task_counts(client):
    admin_email = "dashboard-admin@example.com"
    _register_user(client, name="Dashboard Admin", email=admin_email, role="org_admin")
    admin_auth = _login(client, email=admin_email)

    org_response = client.post(
        "/organizations",
        json={"name": "Dashboard Org", "description": "org for dashboard checks"},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    org_id = org_response.json()["id"]

    project_one = client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Project A"},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    project_two = client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Project B"},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert project_one.status_code == 200
    assert project_two.status_code == 200

    task_response = client.post(
        "/tasks",
        json={
            "project_id": project_one.json()["id"],
            "title": "Dashboard Task",
            "assignee_id": admin_auth["user"]["id"],
        },
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert task_response.status_code == 200
    second_task_response = client.post(
        "/tasks",
        json={
            "project_id": project_two.json()["id"],
            "title": "Dashboard Task in Project B",
            "assignee_id": admin_auth["user"]["id"],
        },
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert second_task_response.status_code == 200

    dashboard_response = client.get(
        "/dashboard/organization",
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert dashboard_response.status_code == 200
    payload = dashboard_response.json()
    assert payload["total_projects"] >= 2
    assert payload["total_tasks"] >= 1
    assert payload["total_users"] >= 1
    assert payload["active_users"] >= 1

    manager_dashboard = client.get(
        "/dashboard/project-manager",
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert manager_dashboard.status_code == 200, manager_dashboard.text
    assert "tasks_by_member" in manager_dashboard.json()
    assert "tasks_by_priority" in manager_dashboard.json()
    member_tasks = [
        item
        for item in manager_dashboard.json()["tasks_by_member"]
        if item["assignee_id"] == admin_auth["user"]["id"]
    ]
    assert {item["project_id"] for item in member_tasks} == {
        project_one.json()["id"],
        project_two.json()["id"],
    }


def test_my_tasks_dashboard_counts_assigned_tasks(client):
    admin_email = "dashboard-admin-2@example.com"
    member_email = "dashboard-member@example.com"
    _register_user(client, name="Dashboard Admin 2", email=admin_email, role="org_admin")
    _register_user(client, name="Dashboard Member", email=member_email, role="team_member")
    admin_auth = _login(client, email=admin_email)
    member_auth = _login(client, email=member_email)

    org_response = client.post(
        "/organizations",
        json={"name": "My Tasks Org", "description": "my tasks dashboard"},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["id"]

    project_response = client.post(
        "/projects",
        json={"organization_id": org_id, "name": "My Tasks Project"},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert project_response.status_code == 200
    project_id = project_response.json()["id"]

    org_member_response = client.post(
        f"/organizations/{org_id}/members",
        json={"user_id": member_auth["user"]["id"], "role": "team_member"},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert org_member_response.status_code == 200
    project_member_response = client.post(
        f"/projects/{project_id}/members",
        json={"user_id": member_auth["user"]["id"]},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert project_member_response.status_code == 200

    task_response = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Assigned Task", "assignee_id": member_auth['user']['id']},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert task_response.status_code == 200

    dashboard_response = client.get(
        "/dashboard/my-tasks",
        headers={"Authorization": f"Bearer {member_auth['access_token']}"},
    )
    assert dashboard_response.status_code == 200
    payload = dashboard_response.json()
    assert payload["my_tasks"] >= 1
