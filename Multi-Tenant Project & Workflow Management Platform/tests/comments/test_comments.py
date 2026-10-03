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


def test_add_comment_and_notification_mentions_user(client):
    admin_email = "comment-admin@example.com"
    member_email = "comment-member@example.com"
    _register_user(client, name="Admin", email=admin_email, role="org_admin")
    member_payload = _register_user(client, name="Member", email=member_email, role="team_member")

    admin_auth = _login(client, email=admin_email)
    member_auth = _login(client, email=member_email)

    org_response = client.post(
        "/organizations",
        json={"name": "Comment Org", "description": "Org for commenting"},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert org_response.status_code == 200, org_response.text
    org_id = org_response.json()["id"]

    project_response = client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Comment Project"},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert project_response.status_code == 200, project_response.text
    project_id = project_response.json()["id"]

    add_member_response = client.post(
        f"/organizations/{org_id}/members",
        json={"user_id": member_payload["user"]["id"], "role": "team_member"},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert add_member_response.status_code == 200, add_member_response.text

    add_project_member_response = client.post(
        f"/projects/{project_id}/members",
        json={"user_id": member_payload["user"]["id"]},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert add_project_member_response.status_code == 200, add_project_member_response.text

    task_response = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Discuss API", "assignee_id": member_payload["user"]["id"]},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert task_response.status_code == 200, task_response.text
    task_id = task_response.json()["id"]

    comment_response = client.post(
        f"/tasks/{task_id}/comments",
        json={"content": "Please review @comment-member@example.com and @Member before we move on."},
        headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
    )
    assert comment_response.status_code == 200, comment_response.text
    assert comment_response.json()["content"].startswith("Please review")

    list_response = client.get(
        f"/tasks/{task_id}/comments",
        headers={"Authorization": f"Bearer {member_auth['access_token']}"},
    )
    assert list_response.status_code == 200, list_response.text
    comments = list_response.json()
    assert len(comments) == 1
    assert "@comment-member@example.com" in comments[0]["content"]

    notifications_response = client.get(
        "/notifications",
        headers={"Authorization": f"Bearer {member_auth['access_token']}"},
    )
    assert notifications_response.status_code == 200, notifications_response.text
    assert any("mentioned you" in item["message"] for item in notifications_response.json())


def test_comment_update_requires_author(client):
    admin_email = "comment-author@example.com"
    other_email = "comment-other@example.com"
    _register_user(client, name="Author", email=admin_email, role="org_admin")
    _register_user(client, name="Other", email=other_email, role="org_admin")

    author_auth = _login(client, email=admin_email)
    other_auth = _login(client, email=other_email)

    org_response = client.post(
        "/organizations",
        json={"name": "Comment Update Org", "description": "Comment update tests"},
        headers={"Authorization": f"Bearer {author_auth['access_token']}"},
    )
    org_id = org_response.json()["id"]

    project_response = client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Comment Update Project"},
        headers={"Authorization": f"Bearer {author_auth['access_token']}"},
    )
    project_id = project_response.json()["id"]

    task_response = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Comment update task"},
        headers={"Authorization": f"Bearer {author_auth['access_token']}"},
    )
    task_id = task_response.json()["id"]

    create_response = client.post(
        f"/tasks/{task_id}/comments",
        json={"content": "Initial comment"},
        headers={"Authorization": f"Bearer {author_auth['access_token']}"},
    )
    comment_id = create_response.json()["id"]

    update_response = client.put(
        f"/comments/{comment_id}",
        json={"content": "This was edited by someone else"},
        headers={"Authorization": f"Bearer {other_auth['access_token']}"},
    )
    assert update_response.status_code == 403


def test_project_comments_can_be_created_and_listed(client):
    _register_user(client, name="Project Commenter", email="project-commenter@example.com", role="org_admin")
    auth = _login(client, email="project-commenter@example.com")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    organization = client.post("/organizations", json={"name": "Project Comment Org"}, headers=headers)
    project = client.post(
        "/projects", json={"organization_id": organization.json()["id"], "name": "Commentable Project"}, headers=headers
    )

    created = client.post(
        f"/projects/{project.json()['id']}/comments",
        json={"content": "Project-level discussion"},
        headers=headers,
    )
    listed = client.get(f"/projects/{project.json()['id']}/comments", headers=headers)

    assert created.status_code == 200, created.text
    assert created.json()["project_id"] == project.json()["id"]
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["content"] == "Project-level discussion"
