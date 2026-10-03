from tests.conftest import provision_test_user


def register_and_login(client, email, role="org_admin"):
    return provision_test_user(client, name="Audit User", email=email, role=role)


def test_audit_logs_are_tenant_scoped_and_read_only(client):
    admin = register_and_login(client, "audit-admin@example.com")
    member = register_and_login(client, "audit-member@example.com", role="team_member")
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
    member_headers = {"Authorization": f"Bearer {member['access_token']}"}

    organization = client.post("/organizations", json={"name": "Audit Org"}, headers=admin_headers)
    project = client.post(
        "/projects",
        json={"organization_id": organization.json()["id"], "name": "Audited Project"},
        headers=admin_headers,
    )

    logs = client.get(
        f"/audit-logs?organization_id={organization.json()['id']}&page=1&page_size=10",
        headers=admin_headers,
    )
    denied = client.get("/audit-logs", headers=member_headers)

    assert logs.status_code == 200, logs.text
    assert logs.json()["total"] >= 1
    project_event = next(item for item in logs.json()["items"] if item["entity_id"] == project.json()["id"])
    assert project_event["action"] == "PROJECT_CREATED"
    assert project_event["ip_address"]
    assert denied.status_code == 403
