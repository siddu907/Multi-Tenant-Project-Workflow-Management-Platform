from datetime import datetime

from pydantic import BaseModel


class OrganizationMemberResponse(BaseModel):
    id: int
    organization_id: int
    user_id: int
    role: str
    is_active: bool
    joined_at: datetime
