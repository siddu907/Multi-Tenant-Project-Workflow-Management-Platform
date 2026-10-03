from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1)


class CommentUpdate(BaseModel):
    content: str = Field(..., min_length=1)


class CommentResponse(BaseModel):
    id: int
    content: str
    user_id: int
    project_id: int | None = None
    task_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
