from datetime import datetime

from pydantic import BaseModel


class AttachmentResponse(BaseModel):
    id: int
    filename: str
    mime_type: str
    file_size: int
    storage_path: str
    uploaded_by: int
    project_id: int | None = None
    task_id: int | None = None
    created_at: datetime | None = None
