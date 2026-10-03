from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.organization_member import OrganizationMember
    from app.models.project_member import ProjectMember
    from app.models.task import Task
    from app.models.comment import Comment
    from app.models.notification import Notification
    from app.models.audit_log import AuditLog
    from app.models.refresh_token import RefreshToken


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    token_version: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    role: Mapped["Role"] = relationship("Role", back_populates="users")
    organization_memberships: Mapped[list["OrganizationMember"]] = relationship("OrganizationMember", back_populates="user")
    project_memberships: Mapped[list["ProjectMember"]] = relationship("ProjectMember", back_populates="user")
    assigned_tasks: Mapped[list["Task"]] = relationship("Task", foreign_keys="Task.assignee_id", back_populates="assignee")
    reported_tasks: Mapped[list["Task"]] = relationship("Task", foreign_keys="Task.reporter_id", back_populates="reporter")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="user")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="user")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship("RefreshToken", back_populates="user")