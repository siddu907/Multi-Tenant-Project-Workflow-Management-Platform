from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.organization_member import OrganizationMember
    from app.models.project import Project


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    members: Mapped[list["OrganizationMember"]] = relationship("OrganizationMember", back_populates="organization", passive_deletes="all")
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="organization", passive_deletes="all")