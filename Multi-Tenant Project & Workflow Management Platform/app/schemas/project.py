from datetime import date, datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    organization_id: int
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None
    status: str = Field(default="planning", max_length=30)
    start_date: date | None = None
    due_date: date | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    status: str | None = Field(default=None, max_length=30)
    start_date: date | None = None
    due_date: date | None = None


class ProjectMemberCreate(BaseModel):
    user_id: int


class ProjectMemberResponse(BaseModel):
    id: int
    project_id: int
    user_id: int
    is_active: bool
    joined_at: datetime


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    organization_id: int
    owner_id: int
    status: str
    start_date: date | None = None
    due_date: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
