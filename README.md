# Multi-Tenant Project & Workflow Management Platform

This project is a backend-only FastAPI application for a multi-tenant project and workflow management platform.

## Scope

The assignment was implemented in the backend scope only, with the following core concerns:

- JWT authentication and refresh-token flow
- Role-based and resource-based authorization
- Multi-tenant organization boundaries
- Project and task lifecycle management
- Task assignment, status transitions, and dependency handling
- Comments and mentions
- File validation and upload handling
- Notifications and real-time websocket support
- Dashboard endpoints per role
- Audit logging and activity tracking
- Background processing hooks
- Automated backend testing

## Architecture

The application follows a layered backend structure:

Routes -> Dependencies -> Services -> Repositories -> Models -> PostgreSQL

Example modules:

- app/routers
- app/dependencies
- app/services
- app/repositories
- app/models
- app/core
- app/background

## User roles

The backend supports:

- Super Admin
- Organization Admin
- Project Manager
- Team Member
- Viewer

Authorization is enforced both by role and by resource ownership/organization membership.

## Multi-tenant behavior

The system enforces organization isolation so users cannot access resources from another organization's projects, tasks, comments, or files.

Key checks include:

- organization membership validation
- project membership validation
- task access validation
- cross-organization access rejection
- inactive-user restrictions
- role-based route protections

## Authentication and security

Implemented flows include:

- register
- login
- refresh
- logout
- me
- change-password
- protected routes via JWT dependency
- password hashing
- token expiration and refresh token handling
- inactive-user block

Public registration can be controlled with `ALLOW_PUBLIC_REGISTRATION`. The supplied `.env.example` sets it to `false`; when disabled, users must be created by an administrator. When enabled, public registration creates Team Member accounts only. The protected `POST /users` endpoint allows Super Admins to create all supported roles, while Organization Admins can create Project Managers and Team Members.

## Project and task features

Implemented backend features include:

- Organization creation and member management
- Project creation, listing, update, and membership control
- Task creation, update, deletion, assignment, status change, and priority handling
- Valid workflow transitions
- Task dependency tracking with circular dependency prevention
- Comment creation and mention-based notifications
- File upload validation with MIME and size checks

## Notifications and real-time behavior

The backend includes:

- notification APIs
- websocket endpoint for notifications
- mark-as-read support
- fallback REST notification routes
- task/mention/project alerts

## Background processing

Background support is present in app/background for tasks such as:

- file cleanup
- notification generation
### Prerequisites
The project exposes backend dashboard endpoints for different roles, including:
- Python and PostgreSQL must be installed and available. Create a PostgreSQL role and database before running migrations; the application does not create the database for you.
- From the repository root, create a virtual environment and install the dependencies:
- organization-level metrics
```powershell
python -m venv .venv
\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell prevents activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` in that terminal and activate the environment again.

### Configure the environment

Copy the example file and edit `.env`:

```powershell
Copy-Item .env.example .env
```

Set `DATABASE_URL` to the PostgreSQL role, password, host, port, and database you created. The example format is:

```text
DATABASE_URL=postgresql+psycopg2://app_user:your_database_password@localhost:5432/workflow_db
```

Replace `SECRET_KEY` with a unique random value. Generate one with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep the generated value private. Review the remaining settings in `.env.example`, including token lifetimes, upload directory, maximum upload size, and `ALLOW_PUBLIC_REGISTRATION`. The example disables public registration.

### Create the schema

With PostgreSQL running and `.env` configured, apply the Alembic migrations:

```powershell
alembic upgrade head
```

This creates or upgrades the application tables. Tables are not created automatically when the API starts.

### Bootstrap the first Super Admin

The seed command creates the first and only global Super Admin. Provide credentials through PowerShell environment variables; do not put the password in the command itself:

```powershell
$env:SUPER_ADMIN_NAME = "Platform Admin"
$env:SUPER_ADMIN_EMAIL = "admin@example.com"
$env:SUPER_ADMIN_PASSWORD = "replace-with-a-unique-strong-password"
python -m app.seed_super_admin
Remove-Item Env:SUPER_ADMIN_NAME
Remove-Item Env:SUPER_ADMIN_EMAIL
Remove-Item Env:SUPER_ADMIN_PASSWORD
```

After seeding, sign in as that account. Use the protected `POST /users` endpoint to create users and then add them to organizations and projects as needed.

### Run the API

Start the development server from the repository root:

```powershell

## Testing

Open `http://127.0.0.1:8000/docs` for Swagger UI or `http://127.0.0.1:8000/redoc` for ReDoc. The WebSocket notification endpoint is `/ws/notifications` and requires an access token.

### Run the tests
- authorization
Run the automated suite from the repository root:

```powershell
python -m pytest -q
- security rules

### Background notifications

The FastAPI lifespan starts a daily UTC due-soon/overdue notification job. In multi-worker PostgreSQL deployments, an advisory lock prevents simultaneous processing. To run the processor manually for operations or testing:
pytest -q
```powershell

## Setup

1. Create a virtual environment
2. Install requirements
3. Copy `.env.example` to `.env` and configure PostgreSQL and JWT settings
4. Apply the database migrations
5. Run the application with FastAPI/Uvicorn

Example:

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

The application does not create production tables at startup. Use Alembic for schema changes.

Bootstrap the first super-admin account using environment variables (do not expose the password as a command-line argument):

```powershell
$env:SUPER_ADMIN_EMAIL = "admin@example.com"
$env:SUPER_ADMIN_PASSWORD = "use-a-strong-password"
python -m app.seed_super_admin
```

Sign in as the bootstrapped Super Admin and use `POST /users` to create Super Admin, Organization Admin, Project Manager, Team Member, and Viewer accounts.


