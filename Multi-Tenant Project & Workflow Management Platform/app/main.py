from contextvars import Token
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from app.core.exception_handlers import register_exception_handlers
from app.routers import attachments, audit_logs, auth, comments, dashboard, notifications, organizations, projects, tasks, users, websocket
from app.background.scheduler import start_scheduler, stop_scheduler
from app.services.audit_service import current_request_ip


@asynccontextmanager
async def lifespan(app: FastAPI):
	start_scheduler()
	try:
		yield
	finally:
		stop_scheduler()


app = FastAPI(title="Multi-Tenant Project & Workflow Management Platform", version="1.0.0", lifespan=lifespan)
register_exception_handlers(app)


app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, tags=["Users"])
app.include_router(organizations.router, tags=["Organizations"])
app.include_router(projects.router, tags=["Projects"])
app.include_router(tasks.router, tags=["Tasks"])
app.include_router(tasks.dependency_router, tags=["Task Dependencies"])
app.include_router(comments.router, tags=["Comments"])
app.include_router(attachments.router, tags=["Attachments"])
app.include_router(notifications.router, tags=["Notifications"])
app.include_router(dashboard.router, tags=["Dashboard"])
app.include_router(audit_logs.router, tags=["Audit Logs"])
app.include_router(websocket.router, tags=["WebSocket"])
