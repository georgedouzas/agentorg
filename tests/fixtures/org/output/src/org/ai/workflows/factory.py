"""Workflow factory — builds workflows from the spec.

Architecture: `pipeline`.
"""

from agno.agent import Agent as AgnoAgent
from agno.workflow import Parallel, Step
from agno.workflow import Workflow as AgnoWorkflow

from agentorg.core.schema import Spec
from agentorg.core.schema.models import Step as SpecStep


def _build_step(step: SpecStep, agents: dict[str, AgnoAgent]) -> Step | Parallel:
    if step.parallel:
        return Parallel(*[_build_step(sub, agents) for sub in step.parallel])
    return Step(name=step.name, agent=agents[step.agent])  # type: ignore[arg-type]


def build_workflows(spec: Spec, agents: dict[str, AgnoAgent]) -> list[AgnoWorkflow]:
    """Build sequential `pipeline` workflows from the spec."""
    workflows: list[AgnoWorkflow] = []
    for wf in spec.generated.workflows:
        steps = [_build_step(s, agents) for s in wf.steps]
        workflows.append(AgnoWorkflow(name=wf.name, steps=steps))
    return workflows
