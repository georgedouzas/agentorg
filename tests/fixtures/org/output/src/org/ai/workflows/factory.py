"""Workflow factory — registers the spec's workflows as reasoners on the AgentField node.

A workflow is "anything runnable" — typically an agno `Workflow` (`.arun()` over native `Step`/`Parallel`/`Loop`),
or a plain callable that orchestrates step reasoners via `app.call` (with `app.pause` for HITL steps).
`register_workflows` adapts each into a reasoner.
"""

from typing import Any

from agentorg.core.spec import Spec
from agentorg.core.tools.runtime import register_runnable


def register_workflows(app: Any, spec: Spec) -> list[str]:
    """Register every workflow in the spec as a reasoner; return the registered reasoner names."""
    return [register_runnable(app, workflow) for workflow in spec.ai.workflows]
