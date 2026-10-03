from datetime import date, timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

from app.background.deadline_notifications import create_deadline_notifications
from app.database import SessionLocal
from tests.conftest import provision_test_user
def _register_user(client, *, email, name="Notifier", role="org_admin"):
    return provision_test_user(client, name=name, email=email, role=role)


def _login(client, *, email):
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "Secret123!"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_mark_notification_read_and_mark_all_read(client):
    _register_user(client, email="notify-owner@example.com", role="org_admin")
    auth = _login(client, email="notify-owner@example.com")

    response = client.get(
        "/notifications",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)

    if payload:
        notification_id = payload[0]["id"]
        read_response = client.put(
            f"/notifications/{notification_id}/read",
            headers={"Authorization": f"Bearer {auth['access_token']}"},
        )
        assert read_response.status_code == 200
        assert read_response.json()["message"] == "Notification marked as read"

    read_all_response = client.put(
        "/notifications/read-all",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert read_all_response.status_code == 200
    assert read_all_response.json()["message"] == "All notifications marked as read"


def test_api_notification_aliases_are_removed(client):
    assert client.get("/api/notifications").status_code == 404
    assert client.patch("/api/notifications/1/read").status_code == 404
    assert client.patch("/api/notifications/read-all").status_code == 404


def test_notification_websocket_requires_access_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/notifications"):
            pass


def test_notification_websocket_accepts_authenticated_user(client):
    _register_user(client, email="websocket-owner@example.com")
    auth = _login(client, email="websocket-owner@example.com")

    with client.websocket_connect(f"/ws/notifications?token={auth['access_token']}") as websocket:
        websocket.send_text("keepalive")


def test_task_assignment_is_pushed_to_assignee_websocket(client):
    admin = _register_user(client, email="websocket-admin@example.com", name="Websocket Admin")
    member = _register_user(client, email="websocket-member@example.com", name="Websocket Member", role="team_member")
    admin_auth = _login(client, email="websocket-admin@example.com")
    member_auth = _login(client, email="websocket-member@example.com")
    admin_headers = {"Authorization": f"Bearer {admin_auth['access_token']}"}

    organization = client.post("/organizations", json={"name": "Websocket Org"}, headers=admin_headers)
    org_id = organization.json()["id"]
    client.post(
        f"/organizations/{org_id}/members",
        json={"user_id": member["user"]["id"], "role": "team_member"},
        headers=admin_headers,
    )
    project = client.post(
        "/projects", json={"organization_id": org_id, "name": "Websocket Project"}, headers=admin_headers
    )
    project_id = project.json()["id"]
    client.post(
        f"/projects/{project_id}/members",
        json={"user_id": member["user"]["id"]},
        headers=admin_headers,
    )
    with client.websocket_connect(f"/ws/notifications?token={member_auth['access_token']}") as websocket:
        task = client.post(
            "/tasks",
            json={"project_id": project_id, "title": "Realtime assignment", "assignee_id": member["user"]["id"]},
            headers=admin_headers,
        )
        assert task.status_code == 200, task.text
        event = websocket.receive_json()

    assert event["type"] == "task_assigned"
    assert "Realtime assignment" in event["message"]


def test_deadline_notifications_are_created_once_per_day(client):
    today = date.today()
    admin = _register_user(client, email="deadline-admin@example.com", name="Deadline Admin")
    member = _register_user(client, email="deadline-member@example.com", name="Deadline Member", role="team_member")
    admin_auth = _login(client, email="deadline-admin@example.com")
    member_auth = _login(client, email="deadline-member@example.com")
    headers = {"Authorization": f"Bearer {admin_auth['access_token']}"}

    organization = client.post("/organizations", json={"name": "Deadline Org"}, headers=headers)
    org_id = organization.json()["id"]
    client.post(
        f"/organizations/{org_id}/members",
        json={"user_id": member["user"]["id"], "role": "team_member"},
        headers=headers,
    )
    project = client.post("/projects", json={"organization_id": org_id, "name": "Deadline Project"}, headers=headers)
    client.post(
        f"/projects/{project.json()['id']}/members",
        json={"user_id": member["user"]["id"]},
        headers=headers,
    )
    task = client.post(
        "/tasks",
        json={
            "project_id": project.json()["id"],
            "title": "Overdue task",
            "assignee_id": member["user"]["id"],
            "due_date": (today - timedelta(days=1)).isoformat(),
        },
        headers=headers,
    )
    assert task.status_code == 200, task.text

    with client.websocket_connect(f"/ws/notifications?token={member_auth['access_token']}") as websocket:
        with SessionLocal() as db:
            assert create_deadline_notifications(db, today=today) == 1
        overdue_event = websocket.receive_json()

    assert overdue_event["type"] == "task_overdue"
    assert "Overdue task" in overdue_event["message"]

    with SessionLocal() as db:
        assert create_deadline_notifications(db, today=today) == 0

    notifications = client.get("/notifications", headers={"Authorization": f"Bearer {member_auth['access_token']}"})
    assert any(item["type"] == "task_overdue" for item in notifications.json())
