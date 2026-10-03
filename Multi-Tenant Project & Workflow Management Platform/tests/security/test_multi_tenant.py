import uuid

from sqlalchemy import select

from app.database import SessionLocal
from app.models.user import User
from tests.conftest import provision_test_user


def login(client, email, password):
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_cross_org_access_is_blocked(client):
    org1_admin_email = f"org1_{uuid.uuid4().hex[:8]}@example.com"
    org1_admin_password = "Password1!"
    provision_test_user(client, name="Org 1 Admin", email=org1_admin_email, password=org1_admin_password, role="org_admin")
    token1 = login(client, org1_admin_email, org1_admin_password)
    headers1 = {"Authorization": f"Bearer {token1}"}

    org2_admin_email = f"org2_{uuid.uuid4().hex[:8]}@example.com"
    org2_admin_password = "Password1!"
    provision_test_user(client, name="Org 2 Admin", email=org2_admin_email, password=org2_admin_password, role="org_admin")
    token2 = login(client, org2_admin_email, org2_admin_password)
    headers2 = {"Authorization": f"Bearer {token2}"}

    org1 = client.post("/organizations", json={"name": f"Org One {uuid.uuid4().hex[:6]}", "description": "First org"}, headers=headers1)
    org1_id = org1.json()["id"]
    project1 = client.post("/projects", json={"organization_id": org1_id, "name": f"Project A {uuid.uuid4().hex[:6]}"}, headers=headers1)
    project1_id = project1.json()["id"]

    org2 = client.post("/organizations", json={"name": f"Org Two {uuid.uuid4().hex[:6]}", "description": "Second org"}, headers=headers2)

    response = client.get(f"/projects/{project1_id}", headers=headers2)
    assert response.status_code == 403, response.text
    delete_foreign_project = client.delete(f"/projects/{project1_id}", headers=headers2)
    assert delete_foreign_project.status_code == 403, delete_foreign_project.text

    update_foreign_org = client.put(
        f"/organizations/{org2.json()['id']}",
        json={"name": "Unauthorized rename"},
        headers=headers1,
    )
    assert update_foreign_org.status_code == 403, update_foreign_org.text


def test_inactive_user_cannot_authenticate(client):
    email = f"inactive_{uuid.uuid4().hex[:8]}@example.com"
    password = "Password1!"
    client.post("/auth/register", json={"name": "Inactive User", "email": email, "password": password})

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email.lower()))
        assert user is not None
        user.is_active = False
        db.commit()
    finally:
        db.close()

    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401, response.text


def test_organization_admin_user_list_shows_all_users_for_assignment(client):
    first = provision_test_user(client, name="First Admin", email=f"first-{uuid.uuid4().hex}@example.com", password="Password1!", role="org_admin")
    second = provision_test_user(client, name="Second Admin", email=f"second-{uuid.uuid4().hex}@example.com", password="Password1!", role="org_admin")
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}

    client.post("/organizations", json={"name": f"Scoped Users {uuid.uuid4().hex}"}, headers=first_headers)
    users = client.get("/users", headers=first_headers)

    assert users.status_code == 200, users.text
    user_ids = {item["id"] for item in users.json()}
    assert first["user"]["id"] in user_ids
    assert second["user"]["id"] in user_ids


def test_org_admin_can_add_user_to_organization_without_explicit_role(client):
    admin = provision_test_user(client, name="Org Admin", email=f"admin-{uuid.uuid4().hex}@example.com", password="Password1!", role="org_admin")
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
    org = client.post("/organizations", json={"name": f"Member Org {uuid.uuid4().hex[:6]}", "description": "Secure"}, headers=admin_headers)
    org_id = org.json()["id"]

    viewer = provision_test_user(client, name="Viewer Member", email=f"viewer-{uuid.uuid4().hex}@example.com", password="Password1!", role="viewer")
    response = client.post(f"/organizations/{org_id}/members", json={"user_id": viewer["user"]["id"]}, headers=admin_headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user_id"] == viewer["user"]["id"]
    assert payload["role"] == "viewer"


def test_viewer_cannot_create_tasks_in_project(client):
    admin_email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    admin_password = "Password1!"
    provision_test_user(client, name="Org Admin", email=admin_email, password=admin_password, role="org_admin")
    admin_token = login(client, admin_email, admin_password)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    org = client.post("/organizations", json={"name": f"Viewer Org {uuid.uuid4().hex[:6]}", "description": "Secure"}, headers=admin_headers)
    org_id = org.json()["id"]
    project = client.post("/projects", json={"organization_id": org_id, "name": f"Viewer Project {uuid.uuid4().hex[:6]}"}, headers=admin_headers)
    project_id = project.json()["id"]

    viewer_email = f"viewer_{uuid.uuid4().hex[:8]}@example.com"
    viewer_password = "Password1!"
    provision_test_user(client, name="Viewer User", email=viewer_email, password=viewer_password, role="viewer")
    viewer_token = login(client, viewer_email, viewer_password)
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    viewer_me = client.get("/auth/me", headers=viewer_headers)
    viewer_id = viewer_me.json()["id"]

    add_member = client.post(f"/organizations/{org_id}/members", json={"user_id": viewer_id, "role": "viewer"}, headers=admin_headers)
    assert add_member.status_code == 200, add_member.text

    add_project_member = client.post(f"/projects/{project_id}/members", json={"user_id": viewer_id}, headers=admin_headers)
    assert add_project_member.status_code == 200, add_project_member.text

    response = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Viewer task"},
        headers=viewer_headers,
    )
    assert response.status_code in {403, 400}, response.text


def test_team_member_only_accesses_assigned_tasks(client):
    admin_email = f"team_admin_{uuid.uuid4().hex[:8]}@example.com"
    admin_password = "Password1!"
    provision_test_user(client, name="Team Admin", email=admin_email, password=admin_password, role="org_admin")
    admin_token = login(client, admin_email, admin_password)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    org = client.post("/organizations", json={"name": f"Task Org {uuid.uuid4().hex[:6]}", "description": "Task org"}, headers=admin_headers)
    org_id = org.json()["id"]
    project = client.post("/projects", json={"organization_id": org_id, "name": f"Task Project {uuid.uuid4().hex[:6]}"}, headers=admin_headers)
    project_id = project.json()["id"]

    member_email = f"member_{uuid.uuid4().hex[:8]}@example.com"
    member_password = "Password1!"
    provision_test_user(client, name="Team Member", email=member_email, password=member_password, role="team_member")
    member_token = login(client, member_email, member_password)
    member_headers = {"Authorization": f"Bearer {member_token}"}
    member_me = client.get("/auth/me", headers=member_headers)
    member_id = member_me.json()["id"]
    assert client.post(f"/organizations/{org_id}/members", json={"user_id": member_id, "role": "team_member"}, headers=admin_headers).status_code == 200
    assert client.post(f"/projects/{project_id}/members", json={"user_id": member_id}, headers=admin_headers).status_code == 200

    other_email = f"other_member_{uuid.uuid4().hex[:8]}@example.com"
    other_password = "Password1!"
    provision_test_user(client, name="Other Member", email=other_email, password=other_password, role="team_member")
    other_token = login(client, other_email, other_password)
    other_headers = {"Authorization": f"Bearer {other_token}"}
    other_me = client.get("/auth/me", headers=other_headers)
    other_id = other_me.json()["id"]
    assert client.post(f"/organizations/{org_id}/members", json={"user_id": other_id, "role": "team_member"}, headers=admin_headers).status_code == 200
    assert client.post(f"/projects/{project_id}/members", json={"user_id": other_id}, headers=admin_headers).status_code == 200

    task = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Assigned task", "assignee_id": member_id},
        headers=admin_headers,
    )
    assert task.status_code == 200, task.text
    task_id = task.json()["id"]

    member_task = client.get(f"/tasks/{task_id}", headers=member_headers)
    assert member_task.status_code == 200, member_task.text

    other_task = client.get(f"/tasks/{task_id}", headers=other_headers)
    assert other_task.status_code == 403, other_task.text
