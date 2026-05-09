"""Universal providers backed by `org_state` and `knowledge` tables."""

from typing import Any

from sqlalchemy import text

from eng_team.ai.tools.providers import provider
from eng_team.db import get_engine


@provider("state.field", args={"name": str, "user_id": str})
def state_field(name: str, user_id: str = "default") -> Any:
    """Read a single field from org_state. Looks first in `parameters`, then in `data`."""
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT parameters, data FROM org_state WHERE user_id = :uid"),
            {"uid": user_id},
        ).first()
    if row is None:
        return None
    return (row.parameters or {}).get(name) or (row.data or {}).get(name)


@provider("knowledge.count", args={"type": str})
def knowledge_count(type: str = "") -> int:  # noqa: A002
    """Count knowledge rows, optionally filtered by type."""
    sql = "SELECT count(*) AS n FROM knowledge"
    params: dict[str, Any] = {}
    if type:
        sql += " WHERE type = :t"
        params["t"] = type
    with get_engine().connect() as conn:
        row = conn.execute(text(sql), params).first()
    return int(row.n) if row else 0
