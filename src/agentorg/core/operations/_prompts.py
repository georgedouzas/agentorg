"""Render trigger prompt templates with the trigger's context."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime


def render_prompt(
    template: str,
    *,
    trigger_id: str,
    parameters: Mapping[str, object],
    event: object = None,
    body: object = None,
    message: object = None,
    now: datetime | None = None,
) -> str:
    """Fill a trigger prompt's `{now}`, `{trigger_id}`, `{event}`, `{body}`, `{message}` and parameter variables.

    Arguments:
        template: The trigger's prompt.
        trigger_id: The trigger's id.
        parameters: Current parameter values.
        event: The event payload, rendered as JSON.
        body: The webhook body, rendered as JSON.
        message: The queue message body, rendered as JSON.
        now: The fire time; the current UTC time by default.

    Returns:
        prompt: The rendered prompt.
    """
    values: dict[str, object] = {
        **parameters,
        'now': (now or datetime.now(UTC)).isoformat(timespec='minutes'),
        'trigger_id': trigger_id,
        'event': json.dumps(event, default=str),
        'body': json.dumps(body, default=str),
        'message': json.dumps(message, default=str),
    }
    return template.format_map(values)
