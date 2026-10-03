from typing import Any

def apply_filters(query, model, params: dict[str, Any]):
    for field_name, value in params.items():
        if value is None or value == "":
            continue
        column = getattr(model, field_name, None)
        if column is None:
            continue
        if isinstance(value, (list, tuple, set)):
            if value:
                query = query.filter(column.in_(value))
        else:
            query = query.filter(column == value)
    return query
