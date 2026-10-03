from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None = None
    organization_id: int | None = None
    action: str
    entity_type: str
    entity_id: int | None = None
    ip_address: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime
