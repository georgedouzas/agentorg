"""Setup status tool that reports which spec setup steps are done and which are pending."""

import os
from typing import Any

from ._tags import tags


@tags('setup')
def get_setup_status(spec_setup_steps: list[dict[str, Any]] | None = None) -> str:
    """Return the current setup checklist with completion status.

    Arguments:
        spec_setup_steps: List of step dicts from `Spec.runtime.setup`.

    Returns:
        status: A formatted setup checklist.
    """
    steps = spec_setup_steps or []
    if not steps:
        return 'No setup steps declared.'
    lines = ['Setup status:']
    for step in steps:
        variables = step.get('variables') or []
        if variables:
            done = all(os.getenv(v) for v in variables)
            status = 'done' if done else 'PENDING'
            lines.append(f"  [{status}] {step.get('title', step.get('id', '?'))}  ({', '.join(variables)})")
        else:
            lines.append(f"  [unverified] {step.get('title', step.get('id', '?'))}")
    return '\n'.join(lines)
