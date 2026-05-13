"""Per-user org-state CRUD tools — `org_state` table."""

import json
from typing import Any

from sqlalchemy import text

from agentorg.core.tools._engine import get_engine


def get_state(user_id: str = 'default') -> str:
    """Read the org state for a user.

    Returns JSON-encoded {parameters, data}.
    """
    with get_engine().connect() as conn:
        row = conn.execute(
            text('SELECT parameters, data FROM org_state WHERE user_id = :uid'),
            {'uid': user_id},
        ).first()
    if row is None:
        return json.dumps({'configured': False, 'parameters': {}, 'data': {}})
    params = json.loads(row.parameters) if isinstance(row.parameters, str) else (row.parameters or {})
    data = json.loads(row.data) if isinstance(row.data, str) else (row.data or {})
    return json.dumps({'configured': True, 'parameters': params, 'data': data}, indent=2)


def update_state(parameters: dict[str, Any] | None = None, user_id: str = 'default') -> str:
    """Update the org state's parameters for a user.

    Returns confirmation.
    """
    params_json = json.dumps(parameters or {})
    with get_engine().begin() as conn:
        conn.execute(
            text("""
                INSERT INTO org_state (user_id, parameters, data)
                VALUES (:uid, :p, '{}')
                ON CONFLICT (user_id) DO UPDATE
                    SET parameters = excluded.parameters,
                        updated_at = CURRENT_TIMESTAMP
            """),
            {'uid': user_id, 'p': params_json},
        )
    return f"Updated state for user '{user_id}'."


def reset_state(user_id: str = 'default') -> str:
    """Delete the org state row for a user."""
    with get_engine().begin() as conn:
        conn.execute(text('DELETE FROM org_state WHERE user_id = :uid'), {'uid': user_id})
    return f"Reset state for user '{user_id}'."
