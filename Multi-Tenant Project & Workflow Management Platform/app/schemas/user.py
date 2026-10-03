from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    role_id: int
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserSummaryResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    is_active: bool
