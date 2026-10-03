from datetime import date, datetime
from typing import Any


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def serialize_value(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def is_blank(value: Any) -> bool:
    return value is None or value == ""
