from tests.conftest import provision_test_user


def _register_and_login(client, *, email, role="org_admin"):
    return provision_test_user(client, name="Task Assignee", email=email, role=role)


def test_task_assignment_happens_on_creation_and_old_routes_are_removed(client):
    admin = _register_and_login(client, email="task-admin@example.com", role="org_admin")
    member = _register_and_login(client, email="task-member@example.com", role="team_member")
    next_member = _register_and_login(client, email="task-next-member@example.com", role="team_member")

    org_response = client.post(
        "/organizations",
        json={"name": "Assignment Org", "description": "task assignment test"},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    org_id = org_response.json()["id"]
    client.post(
        f"/organizations/{org_id}/members",
        json={"user_id": member["user"]["id"], "role": "team_member"},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    client.post(
        f"/organizations/{org_id}/members",
        json={"user_id": next_member["user"]["id"], "role": "team_member"},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )

    project_response = client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Assignment Project"},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    project_id = project_response.json()["id"]

    invalid_task = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Invalid assignment", "assignee_id": member["user"]["id"]},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert invalid_task.status_code == 400

    task_response = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Task to assign"},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    task_id = task_response.json()["id"]

    removed_assignment_route = client.put(
        f"/tasks/{task_id}/assign",
        json={"assignee_id": member["user"]["id"]},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert removed_assignment_route.status_code == 404

    removed_priority_route = client.put(
        f"/tasks/{task_id}/priority",
        json={"priority": "high"},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert removed_priority_route.status_code == 404

    project_membership = client.post(
        f"/projects/{project_id}/members",
        json={"user_id": member["user"]["id"]},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert project_membership.status_code == 200, project_membership.text
    next_project_membership = client.post(
        f"/projects/{project_id}/members",
        json={"user_id": next_member["user"]["id"]},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert next_project_membership.status_code == 200, next_project_membership.text

    reassign_response = client.put(
        f"/tasks/{task_id}/reassign",
        json={"assignee_id": member["user"]["id"]},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert reassign_response.status_code == 200, reassign_response.text
    assert reassign_response.json()["assignee_id"] == member["user"]["id"]

    reassign_again_response = client.put(
        f"/tasks/{task_id}/reassign",
        json={"assignee_id": next_member["user"]["id"]},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert reassign_again_response.status_code == 200, reassign_again_response.text
    assert reassign_again_response.json()["assignee_id"] == next_member["user"]["id"]

    assign_response = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Initially assigned task", "assignee_id": member["user"]["id"]},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["assignee_id"] == member["user"]["id"]
