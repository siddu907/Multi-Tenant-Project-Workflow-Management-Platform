"""Project member schema definitions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectMemberCreate(BaseModel):
    user_id: int


class ProjectMemberResponse(BaseModel):
    id: int
    project_id: int
    user_id: int
    is_active: bool
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)
