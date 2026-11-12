"""The top-level `Spec` model that a user constructs in `spec.py`."""

from string import Formatter

from pydantic import model_validator

from ._ai import AI
from ._config import SpecModel
from ._knowledge import Knowledge
from ._operations import Operations
from ._org import Org
from ._parameters import Parameter
from ._runtime import Runtime
from ._ui import UI

PROMPT_VARIABLES = frozenset({'now', 'trigger_id', 'event', 'body', 'message'})


class Spec(SpecModel):
    """The whole organization specification."""

    org: Org
    runtime: Runtime
    ai: AI
    operations: Operations
    parameters: list[Parameter]
    knowledge: Knowledge
    ui: UI

    def _validate_targets(self) -> None:
        """Require triggers and the fallback agent to name declared agents or units."""
        targets = {agent.id for agent in self.ai.agents} | {unit.id for unit in self.ai.units}
        unknown = [trigger.id for trigger in self.operations.triggers if trigger.target not in targets]
        if unknown:
            msg = f'Triggers {unknown} target ids that are not declared agents or units.'
            raise ValueError(msg)
        fallback = self.operations.runs.fallback_agent
        if fallback and fallback not in {agent.id for agent in self.ai.agents}:
            msg = f"runs.fallback_agent '{fallback}' is not a declared agent."
            raise ValueError(msg)

    def _validate_env_references(self) -> None:
        """Require every referenced env var to be declared."""
        declared = {var.name for var in self.runtime.env_vars.required + self.runtime.env_vars.optional}
        referenced = {name for agent in self.ai.agents for server in agent.mcp_servers for name in server.env}
        for trigger in self.operations.triggers:
            names = (getattr(trigger, field, None) for field in ('secret_env', 'url_env'))
            referenced |= {name for name in names if name}
        if self.operations.notifications.webhook_url_env:
            referenced.add(self.operations.notifications.webhook_url_env)
        undeclared = sorted(referenced - declared)
        if undeclared:
            msg = f'Env vars {undeclared} are referenced but not declared in runtime.env_vars.'
            raise ValueError(msg)

    def _validate_knowledge_types(self) -> None:
        """Require output knowledge types to be declared."""
        types = {type_.id for type_ in self.knowledge.types}
        unknown = [agent.id for agent in self.ai.agents if agent.output.knowledge_type not in types | {None}]
        if unknown:
            msg = f'Agents {unknown} file output under knowledge types not declared in knowledge.types.'
            raise ValueError(msg)

    def _validate_prompts(self) -> None:
        """Require trigger prompts to use only known variables."""
        allowed = PROMPT_VARIABLES | {parameter.name for parameter in self.parameters}
        for trigger in self.operations.triggers:
            used = {field for _, field, _, _ in Formatter().parse(trigger.prompt) if field}
            unknown = sorted(used - allowed)
            if unknown:
                msg = f"Trigger '{trigger.id}' prompt uses unknown variables {unknown}; allowed: {sorted(allowed)}."
                raise ValueError(msg)

    @model_validator(mode='after')
    def _validate_references(self) -> 'Spec':
        """Validate the references that span domains."""
        self._validate_targets()
        self._validate_env_references()
        self._validate_knowledge_types()
        self._validate_prompts()
        return self
