from tests.conftest import provision_test_user


def _register_and_login(client, *, email, role="org_admin"):
    return provision_test_user(client, name="Project Member User", email=email, role=role)


def test_add_and_remove_project_member(client):
    admin = _register_and_login(client, email="project-admin@example.com", role="org_admin")
    member = _register_and_login(client, email="project-member@example.com", role="team_member")

    org_response = client.post(
        "/organizations",
        json={"name": "Project Member Org", "description": "project member test"},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    org_id = org_response.json()["id"]
    client.post(
        f"/organizations/{org_id}/members",
        json={"user_id": member["user"]["id"], "role": "team_member"},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )

    project_response = client.post(
        "/projects",
        json={"organization_id": org_id, "name": "Project Member Project"},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    project_id = project_response.json()["id"]

    add_member_response = client.post(
        f"/projects/{project_id}/members",
        json={"user_id": member["user"]["id"]},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert add_member_response.status_code == 200
    assert add_member_response.json()["user_id"] == member["user"]["id"]

    duplicate_membership_response = client.post(
        f"/projects/{project_id}/members",
        json={"user_id": member["user"]["id"]},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert duplicate_membership_response.status_code == 409
    assert duplicate_membership_response.json()["detail"] == "User already in project"

    remove_response = client.delete(
        f"/projects/{project_id}/members/{member['user']['id']}",
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert remove_response.status_code == 200
    assert remove_response.json()["message"] == "Project member removed"
