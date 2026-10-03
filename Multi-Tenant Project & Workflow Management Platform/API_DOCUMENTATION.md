# API Documentation

This reference documents the REST API and notification WebSocket for the Multi-Tenant Project & Workflow Management Platform. The interactive OpenAPI reference is available at `/docs` when the API is running; ReDoc is at `/redoc` and the schema is at `/openapi.json`.

## Connection and authentication

Local development base URL:

```text
http://127.0.0.1:8000
```

Except for public registration and login, send the access token in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

`POST /auth/login` returns `access_token`, `refresh_token`, `token_type`, and user information. Use the access token for protected REST requests and the WebSocket. `POST /auth/refresh` accepts a refresh token and returns a new token pair. `POST /auth/logout` revokes the user's active sessions; log in again to obtain a new access token.

Public signup is controlled by `ALLOW_PUBLIC_REGISTRATION`. The provided `.env.example` sets it to `false`. When enabled, public signup creates Team Member accounts. Administrators can create users through `POST /users`, subject to their role's restrictions.

## Roles and access scope

A global Super Admin has platform-wide access. For other users, project and task permissions use the active role assigned in the relevant organization; project membership further scopes access for Team Members and Viewers. Some account-management routes use global roles. Each route applies its own authorization checks, so a successful login does not imply access to every resource.

Typical access rules:

- Super Admin: platform-wide administrative access.
- Organization Admin: administers members and projects within organizations where they have an active Org Admin membership.
- Project Manager: manages projects and tasks in organizations where they have an active Project Manager membership.
- Team Member: accesses project work according to project membership and task assignment; may update status/priority only where permitted.
- Viewer: read-only project access.

## Endpoint index

`{id}` placeholders are integer IDs. Unless noted, JSON request bodies use `Content-Type: application/json`.

### Authentication

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Register a Team Member when public registration is enabled. Returns `201`. |
| POST | `/auth/login` | Authenticate and return access/refresh tokens. |
| GET | `/auth/me` | Return the authenticated user. |
| POST | `/auth/refresh` | Rotate a refresh token and return a new token pair. |
| POST | `/auth/logout` | Revoke the current user's sessions. |
| POST | `/auth/change-password` | Change the authenticated user's password. Body: `{"new_password":"Newpass123!"}`. |

### Users

| Method | Path | Purpose |
|---|---|---|
| GET | `/users` | List users; global Super Admin or global Organization Admin required. |
| POST | `/users` | Create a user. Body: `name`, `email`, `password`, `role`. |
| GET | `/users/{user_id}` | Get a user. |
| PUT | `/users/{user_id}` | Update name and/or email; Super Admin only. |
| PUT | `/users/{user_id}/activate` | Activate a global user account; Super Admin only. |
| PUT | `/users/{user_id}/deactivate` | Deactivate a global user account; Super Admin only. |

Supported global roles are `super_admin`, `org_admin`, `project_manager`, `team_member`, and `viewer`. Organization Admins creating users are limited to Project Manager and Team Member accounts.

### Organizations and members

| Method | Path | Purpose |
|---|---|---|
| GET | `/organizations` | List organizations visible to the user. |
| POST | `/organizations` | Create an organization; global Super Admin or Org Admin. Body: `name`, optional `description`. |
| GET | `/organizations/{organization_id}` | Get an organization. |
| PUT | `/organizations/{organization_id}` | Update organization name and/or description. |
| DELETE | `/organizations/{organization_id}` | Delete an organization. |
| GET | `/organizations/{organization_id}/members` | List organization members. |
| POST | `/organizations/{organization_id}/members` | Add or reactivate a member. Body: `{"user_id":123}`. The member role is derived from the user's current global role when first added. |
| PUT | `/organizations/{organization_id}/members/{user_id}/role` | Set the member's role in this organization. Body: `{"role":"project_manager"}`. |
| PUT | `/organizations/{organization_id}/members/{user_id}/activate` | Activate an organization membership. |
| PUT | `/organizations/{organization_id}/members/{user_id}/deactivate` | Deactivate an organization membership. |
| DELETE | `/organizations/{organization_id}/members/{user_id}` | Remove an organization membership. |

Organization membership roles are `org_admin`, `project_manager`, `team_member`, and `viewer`. Adding an already-active organization member is idempotent; it returns the existing membership rather than creating a duplicate.

### Projects and project members

| Method | Path | Purpose |
|---|---|---|
| GET | `/projects` | List projects visible by organization/project membership. |
| POST | `/projects` | Create a project. Body includes `organization_id`, `name`, optional `description`, `status`, `start_date`, and `due_date`. |
| GET | `/projects/{project_id}` | Get a project. |
| PUT | `/projects/{project_id}` | Update project fields. |
| PUT | `/projects/{project_id}/archive` | Set project status to archived. This marks status; it does not hide the project from lists. |
| DELETE | `/projects/{project_id}` | Delete a project and its dependent records. |
| GET | `/projects/{project_id}/members` | List project members. |
| POST | `/projects/{project_id}/members` | Add a project member. Body: `{"user_id":123}`. User must be an active organization member. |
| DELETE | `/projects/{project_id}/members/{user_id}` | Remove a project member. |

Project status values are `planning`, `active`, `on_hold`, `completed`, and `archived`. Valid status transitions are enforced. An already-added project member is rejected with `409 Conflict`.

### Tasks

| Method | Path | Purpose |
|---|---|---|
| POST | `/tasks` | Create a task, optionally assigning it immediately. |
| GET | `/tasks` | List tasks with filtering, sorting, and pagination. |
| GET | `/tasks/{task_id}` | Get a task. |
| PUT | `/tasks/{task_id}` | Update task details, including priority and actual hours. |
| DELETE | `/tasks/{task_id}` | Delete a task. |
| PUT | `/tasks/{task_id}/reassign` | Reassign an existing task. Body: `{"assignee_id":123}`. |
| PUT | `/tasks/{task_id}/status` | Change task status. Body: `{"status":"todo"}`. Valid transitions and dependencies are enforced. |
| PUT | `/tasks/{task_id}/move` | Move a task to a project in the same organization. Body: `{"project_id":456}`. An existing assignee must be a member of the target project. |

Task creation example:

```json
{
  "project_id": 12,
  "title": "Prepare release notes",
  "description": "Summarize changes for this release",
  "assignee_id": 34,
  "priority": "medium",
  "status": "backlog",
  "due_date": "2026-11-15",
  "estimated_hours": 3
}
```

Task status values are `backlog`, `todo`, `in_progress`, `review`, `blocked`, `done`, and `cancelled`. Priority values are `low`, `medium`, `high`, and `urgent`. Assignees must be active, belong to the task's organization, and be active project members; Viewers cannot be assigned tasks.

`GET /tasks` query parameters:

| Parameter | Meaning |
|---|---|
| `page`, `page_size` | Pagination; defaults are 1 and 20. |
| `status`, `priority` | Filter by task status or priority. |
| `assignee_id`, `project` | Filter by assignee or project ID. |
| `search` | Search task titles. |
| `due_date_from`, `due_date_to` | Filter by due-date range (`YYYY-MM-DD`). |
| `created_date_from`, `created_date_to` | Filter by creation-date range (`YYYY-MM-DD`). |
| `sort_by`, `sort_order` | Sort by supported task fields and `asc`/`desc`. |

The response contains `items`, `page`, `page_size`, and `total`.

### Task dependencies

These routes use the `/api/tasks` prefix:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/tasks/{task_id}/dependencies` | Add a dependency. Body: `{"depends_on_task_id":456}`. |
| GET | `/api/tasks/{task_id}/dependencies` | List dependencies for a task. |
| DELETE | `/api/tasks/{task_id}/dependencies/{dependency_id}` | Remove a dependency. |

A dependency must link tasks in the same project. Circular dependencies are rejected. Note: these routes currently check project access but do not separately block the Viewer role; a Viewer with active project membership can add or remove dependencies.

### Comments and mentions

| Method | Path | Purpose |
|---|---|---|
| POST | `/tasks/{task_id}/comments` | Add a task comment. Body: `{"content":"Please review this, @jane_doe"}`. |
| GET | `/tasks/{task_id}/comments` | List task comments. |
| POST | `/projects/{project_id}/comments` | Add a project comment. Body: `{"content":"Project update"}`. |
| GET | `/projects/{project_id}/comments` | List project comments. |
| PUT | `/comments/{comment_id}` | Update a comment; author only. |
| DELETE | `/comments/{comment_id}` | Delete a comment; author only. |

A mention uses `@name` (spaces represented as underscores) or `@email`. An active user who belongs to the same organization and project receives a mention notification.

### Attachments

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects/{project_id}/attachments` | Upload a project attachment. Use `multipart/form-data`, field name `file`. |
| GET | `/projects/{project_id}/attachments` | List project attachments. |
| POST | `/tasks/{task_id}/attachments` | Upload a task attachment. Use `multipart/form-data`, field name `file`. |
| GET | `/tasks/{task_id}/attachments` | List task attachments. |
| GET | `/attachments/{attachment_id}` | Download the attachment using its original filename. |
| DELETE | `/attachments/{attachment_id}` | Delete an attachment; uploader or organization manager. |

Allowed extensions are `.png`, `.jpg`, `.jpeg`, `.gif`, `.pdf`, `.txt`, `.csv`, `.doc`, and `.docx`. Uploads are checked for configured size limits and supported content signatures/MIME types.

### Notifications

| Method | Path | Purpose |
|---|---|---|
| GET | `/notifications` | List the authenticated user's notifications, including read state. |
| PUT | `/notifications/{notification_id}/read` | Mark one notification as read. |
| PUT | `/notifications/read-all` | Mark all of the authenticated user's notifications as read. |

The REST API returns stored notification history. For live delivery, connect to the WebSocket described below. The older `/api/notifications` aliases are not registered.

### Dashboards and audit logs

| Method | Path | Purpose |
|---|---|---|
| GET | `/dashboard/organization` | Organization-level project, user, and task counts. |
| GET | `/dashboard/project-manager` | Project Manager metrics, task counts by member/project, and priority. |
| GET | `/dashboard/my-tasks` | Counts for the authenticated user's assigned tasks. |
| GET | `/audit-logs` | List audit events; supports `organization_id`, `action`, `entity_type`, `page`, and `page_size`. |

Dashboard and audit visibility depends on the user's role and active organization memberships.

## WebSocket notifications

The WebSocket endpoint is not included in Swagger's REST OpenAPI path list. Connect with a valid access token:

```text
ws://127.0.0.1:8000/ws/notifications?token=<access_token>
```

The server pushes JSON messages to connected users when relevant events occur. A message contains `id`, `type`, `message`, and `created_at`. Event types include `task_assigned`, `task_reassigned`, `task_status_changed`, `comment_added`, `mention`, `project_member_added`, `task_due_soon`, and `task_overdue`. A frontend must listen for messages and display them; the backend does not provide a notification screen.

## Errors

Errors use the application's standard error response envelope and include an HTTP status. Common statuses include `400` for invalid input, `401` for missing/invalid authentication, `403` for insufficient access, `404` for missing resources, `409` for conflicts such as invalid state transitions or dependency conflicts, `413` for oversized uploads, and `422` for request validation errors.

## Examples and tools

- Import [postman_collection.json](postman_collection.json) into Postman for the REST requests. Set its collection variables, then run Login to save the access token.
- Open `/docs` for interactive OpenAPI/Swagger testing and `/redoc` for the generated ReDoc reference.
- Run automated tests with `python -m pytest -q`.
