from datetime import date, datetime
from typing import TYPE_CHECKING
from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.task import Task
    from app.models.comment import Comment
    from app.models.attachment import Attachment


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planning", index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="projects")
    owner: Mapped["User"] = relationship("User")
    members: Mapped[list["ProjectMember"]] = relationship("ProjectMember", back_populates="project", passive_deletes="all")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="project", passive_deletes="all")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="project", passive_deletes="all")
    attachments: Mapped[list["Attachment"]] = relationship("Attachment", back_populates="project", passive_deletes="all")