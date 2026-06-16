"""Render an in-memory `Spec` to a spec.py source file."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agentorg.core.spec import Spec

from ._models import AgentSpec, CustomTool, StepSpec, TeamSpec, WorkflowSpec

INDENT = '    '


def _py_ident(value: str) -> str:
    """Convert a spec id (which may contain hyphens) to a valid Python identifier."""
    return value.replace('-', '_')


def write_spec(spec: Spec, target: Path, *, custom_tools: Iterable[CustomTool] = ()) -> None:
    """Render `spec` (and any registered custom tools) as spec.py source and write it to `target`.

    Arguments:
        spec: The working spec to render.
        target: Destination file path.
        custom_tools: User-defined tool functions to inline at the top of the rendered file.
    """
    target.write_text(render_spec(spec, custom_tools=custom_tools))


def render_spec(spec: Spec, *, custom_tools: Iterable[CustomTool] = ()) -> str:
    """Render a `Spec` plus optional custom tools as a runnable spec.py source string.

    Arguments:
        spec: The working spec.
        custom_tools: User-defined tool functions to inline.

    Returns:
        source: A Python source string that, when imported, reconstructs the spec.
    """
    agent_specs = [a for a in spec.ai.agents if isinstance(a, AgentSpec)]
    team_specs = [t for t in spec.ai.teams if isinstance(t, TeamSpec)]
    workflow_specs = [w for w in spec.ai.workflows if isinstance(w, WorkflowSpec)]
    custom_tool_list = list(custom_tools)

    custom_names = {c.name for c in custom_tool_list}
    builtin_tool_names = sorted({t for a in agent_specs for t in a.tools if t not in custom_names})
    needs_step = bool(workflow_specs)

    sections: list[str] = [
        _render_header(spec),
        _render_imports(builtin_tool_names, needs_team=bool(team_specs), needs_workflow=needs_step),
        *(t.source.rstrip() for t in custom_tool_list),
        *(_render_make_agent_call(a) for a in agent_specs),
        *(_render_make_team_call(t) for t in team_specs),
        *(_render_make_workflow_call(w) for w in workflow_specs),
        _render_spec_assignment(spec, agent_specs, team_specs, workflow_specs),
    ]
    return '\n\n\n'.join(s for s in sections if s) + '\n'


def _render_header(spec: Spec) -> str:
    return f'"""Spec for {spec.org.name}."""'


def _render_imports(builtin_tool_names: list[str], *, needs_team: bool, needs_workflow: bool) -> str:
    """Build the import block, sorted so the output is deterministic."""
    lines: list[str] = []
    if needs_workflow:
        lines.append('from agno.workflow import Step')
    if builtin_tool_names:
        lines.append(f'from agentorg.core.agents.tools import {", ".join(builtin_tool_names)}')
    factories = ['make_agent']
    if needs_team:
        factories.append('make_team')
    if needs_workflow:
        factories.append('make_workflow')
    lines.append(f'from agentorg.core.agents.framework.agno import {", ".join(factories)}')
    lines.append('from agentorg.core.spec import (')
    for symbol in (
        'AI',
        'UI',
        'AppUI',
        'EmptyState',
        'EnvVar',
        'EnvVars',
        'GroupRef',
        'Infra',
        'Knowledge',
        'KnowledgeType',
        'KnowledgeTypeMetadataField',
        'Org',
        'OverviewBlock',
        'Parameter',
        'PrincipleSection',
        'Principles',
        'Runtime',
        'SetupStep',
        'Spec',
    ):
        lines.append(f'{INDENT}{symbol},')
    lines.append(')')
    return '\n'.join(lines)


def _render_make_agent_call(agent: AgentSpec) -> str:
    """Render `<agent_id> = make_agent(...)`. `tools` references imported callables by bare name."""
    fields: list[str] = [
        f'model={python_literal(agent.model, 1)}',
        f'name={python_literal(agent.name, 1)}',
        f'agent_id={python_literal(agent.agent_id, 1)}',
        f'role={python_literal(agent.role, 1)}',
    ]
    if agent.tools:
        fields.append(f'tools=[{", ".join(agent.tools)}]')
    fields.extend(
        _optional_list_fields(
            agent,
            ('in_scope', 'workflow', 'when_to_act', 'out_of_scope', 'style', 'principles'),
        ),
    )
    fields.extend(_optional_str_fields(agent, ('introduction', 'description', 'additional_context')))
    body = ',\n'.join(INDENT + f for f in fields)
    return f'{_py_ident(agent.agent_id)} = make_agent(\n{body},\n)'


def _render_make_team_call(team: TeamSpec) -> str:
    """Render `<team_id> = make_team(...)`. Member references resolve to module-level agent identifiers."""
    fields: list[str] = [
        f'model={python_literal(team.model, 1)}',
        f'name={python_literal(team.name, 1)}',
        f'team_id={python_literal(team.team_id, 1)}',
        f'role={python_literal(team.role, 1)}',
        f'members=[{", ".join(_py_ident(m) for m in team.member_ids)}]',
        f'mode={python_literal(team.mode, 1)}',
    ]
    fields.extend(
        _optional_list_fields(
            team,
            ('workflow', 'in_scope', 'out_of_scope', 'when_to_act', 'style', 'principles'),
        ),
    )
    fields.extend(_optional_str_fields(team, ('introduction', 'description', 'additional_context')))
    body = ',\n'.join(INDENT + f for f in fields)
    return f'{_py_ident(team.team_id)} = make_team(\n{body},\n)'


def _render_make_workflow_call(workflow: WorkflowSpec) -> str:
    """Render `<workflow_id> = make_workflow(...)`. Step `agent_id` resolves to a bare identifier."""
    step_lines = [_render_step(s) for s in workflow.steps]
    steps_body = ',\n'.join(INDENT * 2 + s for s in step_lines)
    fields: list[str] = [
        f'name={python_literal(workflow.name, 1)}',
        f'workflow_id={python_literal(workflow.workflow_id, 1)}',
        f'steps=[\n{steps_body},\n{INDENT}]',
    ]
    if workflow.description:
        fields.append(f'description={python_literal(workflow.description, 1)}')
    body = ',\n'.join(INDENT + f for f in fields)
    return f'{_py_ident(workflow.workflow_id)} = make_workflow(\n{body},\n)'


def _render_step(step: StepSpec) -> str:
    """Render one `Step(name=..., agent=<agent_id>, [requires_output_review=...])` call."""
    parts = [f'name={python_literal(step.name, 0)}', f'agent={_py_ident(step.agent_id)}']
    if step.requires_output_review:
        parts.append('requires_output_review=True')
    return f'Step({", ".join(parts)})'


def _optional_list_fields(item: BaseModel, fields: tuple[str, ...]) -> list[str]:
    """Render `field=[...]` lines for non-empty list fields only."""
    out: list[str] = []
    for name in fields:
        value = getattr(item, name)
        if value:
            out.append(f'{name}={python_literal(value, 1)}')
    return out


def _optional_str_fields(item: BaseModel, fields: tuple[str, ...]) -> list[str]:
    """Render `field='...'` lines for non-empty string fields only."""
    out: list[str] = []
    for name in fields:
        value = getattr(item, name)
        if value:
            out.append(f'{name}={python_literal(value, 1)}')
    return out


def _render_spec_assignment(
    spec: Spec,
    agent_specs: list[AgentSpec],
    team_specs: list[TeamSpec],
    workflow_specs: list[WorkflowSpec],
) -> str:
    """Render the top-level `spec = Spec(...)`. ai.{agents,teams,workflows} use bare identifiers."""
    fields = [
        f'org={python_literal(spec.org, 1)}',
        f'runtime={python_literal(spec.runtime, 1)}',
        f'ai=AI(\n'
        f'{INDENT * 2}framework={python_literal(spec.ai.framework, 2)},\n'
        f'{INDENT * 2}agents=[{", ".join(_py_ident(a.agent_id) for a in agent_specs)}],\n'
        f'{INDENT * 2}teams=[{", ".join(_py_ident(t.team_id) for t in team_specs)}],\n'
        f'{INDENT * 2}workflows=[{", ".join(_py_ident(w.workflow_id) for w in workflow_specs)}],\n'
        f'{INDENT})',
        f'parameters={python_literal(spec.parameters, 1)}',
        f'knowledge={python_literal(spec.knowledge, 1)}',
        f'ui={python_literal(spec.ui, 1)}',
    ]
    body = ',\n'.join(INDENT + f for f in fields)
    return f'spec = Spec(\n{body},\n)'


def python_literal(value: Any, depth: int = 0) -> str:  # noqa: ANN401, PLR0911  (typed-recursive renderer)
    """Render `value` as a Python expression source string suitable for embedding in spec.py.

    Pydantic models become `ClassName(field=...)` constructor calls; lists and dicts pretty-print
    with their contents recursively rendered. Falls back to `repr()` for primitives.

    Arguments:
        value: The value to render.
        depth: Current indentation depth (number of `INDENT` units).

    Returns:
        source: A Python expression as a source string.
    """
    if isinstance(value, BaseModel):
        klass = type(value).__name__
        field_strs = [
            f'{INDENT * (depth + 1)}{name}={python_literal(getattr(value, name), depth + 1)}'
            for name in type(value).model_fields
        ]
        if not field_strs:
            return f'{klass}()'
        body = ',\n'.join(field_strs)
        return f'{klass}(\n{body},\n{INDENT * depth})'
    if isinstance(value, list):
        if not value:
            return '[]'
        items = [f'{INDENT * (depth + 1)}{python_literal(v, depth + 1)}' for v in value]
        body = ',\n'.join(items)
        return f'[\n{body},\n{INDENT * depth}]'
    if isinstance(value, dict):
        if not value:
            return '{}'
        items = [
            f'{INDENT * (depth + 1)}{python_literal(k, depth + 1)}: {python_literal(v, depth + 1)}'
            for k, v in value.items()
        ]
        body = ',\n'.join(items)
        return f'{{\n{body},\n{INDENT * depth}}}'
    return repr(value)
