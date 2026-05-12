"""Generic org-state tools — read/write per-user structured state.

State has two parts:
- `parameters`: charter parameters (user-editable, drives prompts and validation).
- `data`: operational state (agent-managed, e.g. positions/decisions/etc).
"""

import json
from typing import Any

from sqlalchemy import text

from eng_team.db import get_engine

DEFAULT_USER_ID = "default"


def get_state(user_id: str = DEFAULT_USER_ID) -> str:
    """Return the full org state as JSON, including parameters and data.

    Args:
        user_id: Per-user state key (defaults to 'default').
    """
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT parameters, data FROM org_state WHERE user_id = :uid"),
            {"uid": user_id},
        ).first()
    if row is None:
        return json.dumps({"configured": False, "parameters": {}, "data": {}}, indent=2)
    return json.dumps(
        {"configured": True, "parameters": row.parameters or {}, "data": row.data or {}},
        indent=2,
    )


def update_state(
    parameters_update: dict[str, Any] | None = None,
    data_update: dict[str, Any] | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> str:
    """Merge updates into the org state.

    Args:
        parameters_update: Charter parameters to set/update (merged into existing).
        data_update: Operational data to set/update (merged into existing).
        user_id: Per-user state key.
    """
    with get_engine().begin() as conn:
        row = conn.execute(
            text("SELECT parameters, data FROM org_state WHERE user_id = :uid"),
            {"uid": user_id},
        ).first()
        params = (row.parameters if row else None) or {}
        data = (row.data if row else None) or {}
        if parameters_update:
            params = {**params, **parameters_update}
        if data_update:
            data = {**data, **data_update}
        conn.execute(
            text("""
                INSERT INTO org_state (user_id, parameters, data, updated_at)
                VALUES (:uid, CAST(:p AS JSONB), CAST(:d AS JSONB), NOW())
                ON CONFLICT (user_id) DO UPDATE
                    SET parameters = EXCLUDED.parameters,
                        data       = EXCLUDED.data,
                        updated_at = NOW()
            """),
            {"uid": user_id, "p": json.dumps(params), "d": json.dumps(data)},
        )
    return f"State updated for user '{user_id}'."


def reset_state(user_id: str = DEFAULT_USER_ID, parameters: dict[str, Any] | None = None) -> str:
    """Reset operational data (preserve or replace parameters)."""
    with get_engine().begin() as conn:
        conn.execute(
            text("""
                INSERT INTO org_state (user_id, parameters, data, updated_at)
                VALUES (:uid, CAST(:p AS JSONB), '{}', NOW())
                ON CONFLICT (user_id) DO UPDATE
                    SET parameters = EXCLUDED.parameters,
                        data       = '{}',
                        updated_at = NOW()
            """),
            {"uid": user_id, "p": json.dumps(parameters or {})},
        )
    return f"State reset for user '{user_id}'."
