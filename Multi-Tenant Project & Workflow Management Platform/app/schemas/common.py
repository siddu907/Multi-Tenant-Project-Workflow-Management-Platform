from typing import Any

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class EmptySuccessResponse(BaseModel):
    success: bool = True


class PaginationResponse(BaseModel):
    items: list[Any]
    page: int
    page_size: int
    total: int
