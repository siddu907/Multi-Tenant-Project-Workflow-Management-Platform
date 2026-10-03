import uuid

from tests.conftest import provision_test_user


def login(client, email, password):
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_admin_can_manage_org_and_project(client):
    email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    password = "Password1!"
    provision_test_user(client, name="Org Admin", email=email, password=password, role="org_admin")
    token = login(client, email, password)
    headers = {"Authorization": f"Bearer {token}"}

    org_response = client.post("/organizations", json={"name": "Admin Org", "description": "admin org"}, headers=headers)
    assert org_response.status_code == 200, org_response.text
    org_id = org_response.json()["id"]

    project_response = client.post("/projects", json={"organization_id": org_id, "name": "Admin Project"}, headers=headers)
    assert project_response.status_code == 200, project_response.text
    project_id = project_response.json()["id"]

    task_response = client.post("/tasks", json={"project_id": project_id, "title": "Admin Task"}, headers=headers)
    assert task_response.status_code == 200, task_response.text

    task = client.get(f"/tasks/{task_response.json()['id']}", headers=headers)
    assert task.status_code == 200, task.text


def test_manager_can_access_owned_project_but_not_other_org(client):
    admin_email = f"manager_admin_{uuid.uuid4().hex[:8]}@example.com"
    admin_password = "Password1!"
    provision_test_user(client, name="Manager Admin", email=admin_email, password=admin_password, role="org_admin")
    admin_token = login(client, admin_email, admin_password)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    org_a = client.post("/organizations", json={"name": "Org A", "description": "first org"}, headers=admin_headers)
    org_a_id = org_a.json()["id"]
    project_a = client.post("/projects", json={"organization_id": org_a_id, "name": "Project A"}, headers=admin_headers)
    project_a_id = project_a.json()["id"]

    org_b = client.post("/organizations", json={"name": "Org B", "description": "second org"}, headers=admin_headers)
    org_b_id = org_b.json()["id"]
    project_b = client.post("/projects", json={"organization_id": org_b_id, "name": "Project B"}, headers=admin_headers)
    project_b_id = project_b.json()["id"]

    manager_email = f"project_manager_{uuid.uuid4().hex[:8]}@example.com"
    manager_password = "Password1!"
    provision_test_user(client, name="Project Manager", email=manager_email, password=manager_password, role="project_manager")
    manager_token = login(client, manager_email, manager_password)
    manager_headers = {"Authorization": f"Bearer {manager_token}"}
    manager_me = client.get("/auth/me", headers=manager_headers)
    manager_id = manager_me.json()["id"]

    add_to_org = client.post(f"/organizations/{org_a_id}/members", json={"user_id": manager_id, "role": "project_manager"}, headers=admin_headers)
    assert add_to_org.status_code == 200, add_to_org.text
    add_to_project = client.post(f"/projects/{project_a_id}/members", json={"user_id": manager_id}, headers=admin_headers)
    assert add_to_project.status_code == 200, add_to_project.text

    allowed = client.get(f"/projects/{project_a_id}", headers=manager_headers)
    assert allowed.status_code == 200, allowed.text

    blocked = client.get(f"/projects/{project_b_id}", headers=manager_headers)
    assert blocked.status_code == 403, blocked.text


def test_member_can_only_manage_assigned_tasks(client):
    admin_email = f"member_admin_{uuid.uuid4().hex[:8]}@example.com"
    admin_password = "Password1!"
    provision_test_user(client, name="Member Admin", email=admin_email, password=admin_password, role="org_admin")
    admin_token = login(client, admin_email, admin_password)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    org = client.post("/organizations", json={"name": "Member Org", "description": "member org"}, headers=admin_headers)
    org_id = org.json()["id"]
    project = client.post("/projects", json={"organization_id": org_id, "name": "Member Project"}, headers=admin_headers)
    project_id = project.json()["id"]

    member_email = f"team_member_{uuid.uuid4().hex[:8]}@example.com"
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

    task = client.post("/tasks", json={"project_id": project_id, "title": "Assigned Task", "assignee_id": member_id}, headers=admin_headers)
    assert task.status_code == 200, task.text
    task_id = task.json()["id"]

    assigned = client.get(f"/tasks/{task_id}", headers=member_headers)
    assert assigned.status_code == 200, assigned.text

    unassigned = client.get(f"/tasks/{task_id}", headers=other_headers)
    assert unassigned.status_code == 403, unassigned.text


def test_viewer_has_read_only_access(client):
    admin_email = f"viewer_admin_{uuid.uuid4().hex[:8]}@example.com"
    admin_password = "Password1!"
    provision_test_user(client, name="Viewer Admin", email=admin_email, password=admin_password, role="org_admin")
    admin_token = login(client, admin_email, admin_password)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    org = client.post("/organizations", json={"name": "Viewer Org", "description": "viewer org"}, headers=admin_headers)
    org_id = org.json()["id"]
    project = client.post("/projects", json={"organization_id": org_id, "name": "Viewer Project"}, headers=admin_headers)
    project_id = project.json()["id"]

    viewer_email = f"viewer_{uuid.uuid4().hex[:8]}@example.com"
    viewer_password = "Password1!"
    provision_test_user(client, name="Read Only Viewer", email=viewer_email, password=viewer_password, role="viewer")
    viewer_token = login(client, viewer_email, viewer_password)
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    viewer_me = client.get("/auth/me", headers=viewer_headers)
    viewer_id = viewer_me.json()["id"]
    assert client.post(f"/organizations/{org_id}/members", json={"user_id": viewer_id, "role": "viewer"}, headers=admin_headers).status_code == 200
    assert client.post(f"/projects/{project_id}/members", json={"user_id": viewer_id}, headers=admin_headers).status_code == 200

    task = client.post("/tasks", json={"project_id": project_id, "title": "Viewer Visible Task"}, headers=admin_headers)
    assert task.status_code == 200, task.text
    task_id = task.json()["id"]

    project_access = client.get(f"/projects/{project_id}", headers=viewer_headers)
    assert project_access.status_code == 200, project_access.text

    task_access = client.get(f"/tasks/{task_id}", headers=viewer_headers)
    assert task_access.status_code == 200, task_access.text

    blocked = client.post("/tasks", json={"project_id": project_id, "title": "Viewer creates task"}, headers=viewer_headers)
    assert blocked.status_code in {403, 400}, blocked.text
