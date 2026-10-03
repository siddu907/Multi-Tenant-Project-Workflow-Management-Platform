from datetime import date, datetime
from typing import TYPE_CHECKING
from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User
    from app.models.task_dependency import TaskDependency
    from app.models.comment import Comment
    from app.models.attachment import Attachment


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="backlog", index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    estimated_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="tasks")
    assignee: Mapped["User | None"] = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_tasks")
    reporter: Mapped["User"] = relationship("User", foreign_keys=[reporter_id], back_populates="reported_tasks")
    dependencies: Mapped[list["TaskDependency"]] = relationship("TaskDependency", foreign_keys="TaskDependency.task_id", back_populates="task", passive_deletes="all")
    dependent_on: Mapped[list["TaskDependency"]] = relationship("TaskDependency", foreign_keys="TaskDependency.depends_on_task_id", back_populates="depends_on_task", passive_deletes="all")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="task", passive_deletes="all")
    attachments: Mapped[list["Attachment"]] = relationship("Attachment", back_populates="task", passive_deletes="all")