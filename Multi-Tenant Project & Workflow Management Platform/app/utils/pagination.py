from dataclasses import dataclass
from typing import Any, Sequence

@dataclass
class PaginatedResponse:
    items: list[Any]
    total: int
    page: int
    size: int
    pages: int = 0

    def to_dict(self):
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "size": self.size,
            "pages": self.pages,
        }


def paginate_items(items: Sequence[Any], page: int = 1, size: int = 20) -> PaginatedResponse:
    page = max(1, int(page))
    size = max(1, int(size))
    total = len(items)
    pages = (total + size - 1) // size if total else 0
    start = (page - 1) * size
    end = start + size
    return PaginatedResponse(
        items=list(items[start:end]),
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
