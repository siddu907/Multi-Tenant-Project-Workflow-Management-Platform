from tests.conftest import provision_test_user


def _register_and_login(client, *, email, name="Org User", role="org_admin"):
    return provision_test_user(client, name=name, email=email, role=role)


def test_create_and_list_organizations(client):
    auth = _register_and_login(client, email="org-create@example.com")
    create_response = client.post(
        "/organizations",
        json={"name": "Alpha Org", "description": "First org"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["name"] == "Alpha Org"

    list_response = client.get(
        "/organizations",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert list_response.status_code == 200
    orgs = list_response.json()
    assert any(item["name"] == "Alpha Org" for item in orgs)


def test_update_organization(client):
    auth = _register_and_login(client, email="org-update@example.com")
    create_response = client.post(
        "/organizations",
        json={"name": "Before Update", "description": "old description"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    org_id = create_response.json()["id"]

    update_response = client.put(
        f"/organizations/{org_id}",
        json={"name": "After Update", "description": "new description"},
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "After Update"


def test_super_admin_creates_organization_without_becoming_member(client):
    super_admin = provision_test_user(
        client,
        name="Platform Super Admin",
        email="organization-super-admin@example.com",
        role="super_admin",
    )
    headers = {"Authorization": f"Bearer {super_admin['access_token']}"}

    response = client.post(
        "/organizations",
        json={"name": "Super Admin Created Org"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    organization_id = response.json()["id"]

    members = client.get(f"/organizations/{organization_id}/members", headers=headers)
    assert members.status_code == 200, members.text
    assert members.json() == []

    profile = client.get("/auth/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["role"] == "super_admin"
