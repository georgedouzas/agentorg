"""Setup status tool that reports which spec setup steps are done and which are pending."""

import json
import os
from typing import Any

from ._tags import tags


@tags('setup')
def get_setup_status(spec_setup_steps: list[dict[str, Any]] | None = None) -> str:
    """Return the current setup checklist with per-step completion.

    Arguments:
        spec_setup_steps: List of step dicts from `Spec.runtime.setup`.

    Returns:
        status: JSON-encoded `{'steps': [...], 'total': int, 'blocked_count': int,
            'pending_count': int, 'all_done': bool}`. Each step carries `completed`
            (True / False / None for env-less steps) and `missing_vars`.
    """
    steps_out: list[dict[str, Any]] = []
    blocked = pending = 0
    for step in spec_setup_steps or []:
        entry = dict(step)
        variables = entry.get('variables') or []
        if variables:
            missing = [v for v in variables if not os.getenv(v)]
            entry['completed'] = not missing
            entry['missing_vars'] = missing
            if missing:
                blocked += 1
        else:
            entry['completed'] = None
            entry['missing_vars'] = []
            pending += 1
        steps_out.append(entry)
    total = len(steps_out)
    return json.dumps(
        {
            'steps': steps_out,
            'total': total,
            'blocked_count': blocked,
            'pending_count': pending,
            'all_done': total > 0 and blocked == 0 and pending == 0,
        },
    )
