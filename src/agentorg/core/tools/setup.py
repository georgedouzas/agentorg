"""Setup-status tool — reports which spec setup steps are done and which are pending."""

import os
from typing import Any


def get_setup_status(spec_setup_steps: list[dict[str, Any]] | None = None) -> str:
    """Return the current setup checklist with completion status.

    Args:
        spec_setup_steps: List of step dicts from Spec.setup.steps (already serialised by the runtime).
                          Env-var steps are auto-detected; CLI/manual steps stay 'unverified'.
    """
    steps = spec_setup_steps or []
    if not steps:
        return 'No setup steps declared.'
    lines = ['Setup status:']
    for step in steps:
        vars_required = step.get('vars') or []
        if vars_required:
            done = all(os.getenv(v) for v in vars_required)
            status = 'done' if done else 'PENDING'
            lines.append(f"  [{status}] {step.get('title', step.get('id', '?'))}  ({', '.join(vars_required)})")
        else:
            lines.append(f"  [unverified] {step.get('title', step.get('id', '?'))}")
    return '\n'.join(lines)
