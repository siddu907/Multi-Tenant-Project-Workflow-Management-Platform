from datetime import date, datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    project_id: int
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    assignee_id: int | None = None
    priority: str = Field(default="medium", max_length=20)
    status: str = Field(default="backlog", max_length=30)
    due_date: date | None = None
    estimated_hours: float | None = Field(default=None, ge=0)
    actual_hours: float | None = Field(default=None, ge=0)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: str | None = Field(default=None, max_length=20)
    due_date: date | None = None
    estimated_hours: float | None = Field(default=None, ge=0)
    actual_hours: float | None = Field(default=None, ge=0)


class TaskStatusUpdate(BaseModel):
    status: str = Field(..., max_length=30)


class TaskPriorityUpdate(BaseModel):
    priority: str = Field(..., max_length=20)


class TaskAssignmentUpdate(BaseModel):
    assignee_id: int


class TaskMoveRequest(BaseModel):
    project_id: int


class TaskDependencyCreate(BaseModel):
    depends_on_task_id: int


class TaskDependencyResponse(BaseModel):
    id: int
    task_id: int
    depends_on_task_id: int


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    project_id: int
    assignee_id: int | None = None
    reporter_id: int
    priority: str
    status: str
    due_date: date | None = None
    estimated_hours: float | None = None
    actual_hours: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
