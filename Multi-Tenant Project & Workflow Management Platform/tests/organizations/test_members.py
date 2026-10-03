from tests.conftest import provision_test_user


def _register_and_login(client, *, email, role="org_admin"):
    return provision_test_user(client, name="Member User", email=email, role=role)


def test_add_and_deactivate_organization_member(client):
    admin = _register_and_login(client, email="admin-members@example.com", role="org_admin")
    member = _register_and_login(client, email="org-member@example.com", role="team_member")

    org_response = client.post(
        "/organizations",
        json={"name": "Member Org", "description": "member management"},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    org_id = org_response.json()["id"]

    add_member_response = client.post(
        f"/organizations/{org_id}/members",
        json={"user_id": member["user"]["id"]},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert add_member_response.status_code == 200
    assert add_member_response.json()["user_id"] == member["user"]["id"]
    assert add_member_response.json()["role"] == "team_member"

    duplicate = client.post(
        f"/organizations/{org_id}/members",
        json={"user_id": member["user"]["id"]},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["user_id"] == member["user"]["id"]
    assert duplicate.json()["role"] == "team_member"

    deactivate_response = client.put(
        f"/organizations/{org_id}/members/{member['user']['id']}/deactivate",
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["message"] == "Member deactivated"

    reactivated = client.post(
        f"/organizations/{org_id}/members",
        json={"user_id": member["user"]["id"]},
        headers={"Authorization": f"Bearer {admin['access_token']}"},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True
    assert reactivated.json()["role"] == "team_member"


def test_updating_organization_member_to_invalid_role_is_rejected(client):
    admin = _register_and_login(client, email="admin-invalid-member-role@example.com", role="org_admin")
    member = _register_and_login(client, email="member-invalid-role@example.com", role="team_member")
    headers = {"Authorization": f"Bearer {admin['access_token']}"}

    organization = client.post("/organizations", json={"name": "Invalid Member Role Org"}, headers=headers)
    organization_id = organization.json()["id"]
    added = client.post(
        f"/organizations/{organization_id}/members",
        json={"user_id": member["user"]["id"]},
        headers=headers,
    )
    assert added.status_code == 200, added.text

    response = client.put(
        f"/organizations/{organization_id}/members/{member['user']['id']}/role",
        json={"role": "invalid_role"},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid organization member role"
