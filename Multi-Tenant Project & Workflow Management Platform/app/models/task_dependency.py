from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.task import Task

class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    depends_on_task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)

    task: Mapped["Task"] = relationship("Task", foreign_keys=[task_id], back_populates="dependencies")
    depends_on_task: Mapped["Task"] = relationship("Task", foreign_keys=[depends_on_task_id], back_populates="dependent_on")

    __table_args__ = (UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),)