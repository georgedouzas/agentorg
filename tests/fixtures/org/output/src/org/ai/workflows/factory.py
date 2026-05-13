"""Workflow factory — returns the workflows declared in `spec.py`.

The user constructs `agno.Workflow(...)` directly (with native `Step`/`Parallel`/`Loop`/HITL flags), so this factory is
a thin lookup that returns them in order.
"""

from agno.workflow import Workflow

from agentorg.core.schema import Spec


def build_workflows(spec: Spec) -> list[Workflow]:
    """Return the workflows declared in the spec, in the order they appear."""
    return list(spec.workflows)
