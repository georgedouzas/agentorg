"""Render an organization from a single `spec.py` file.

Input: a path to a `spec.py` file in which the user constructs a `Spec(...)` instance named `spec`. The file may also
define custom tool functions used by the agents.

Output: a project directory with:
  - The renderer's template tree (pyproject, README, frontend, factory boilerplate, ...) materialised against the
    spec's data.
  - The user's `spec.py` copied into `<output>/src/<package>/spec.py`, so the rendered runtime can import its agents
    and tools at boot.
"""

import runpy
import shutil
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

from agno.agent import Agent as AgnoAgent
from agno.team import Team as AgnoTeam
from agno.workflow import Step as AgnoStep
from agno.workflow import Workflow as AgnoWorkflow
from jinja2 import Environment, FileSystemLoader, select_autoescape

from agentorg.core.spec import Spec


def _agent_summary(agent: AgnoAgent) -> dict[str, Any]:
    return {'id': agent.id or '', 'name': agent.name or agent.id or '', 'role': agent.role or ''}


def _team_summary(team: AgnoTeam) -> dict[str, Any]:
    members = [m.id for m in (team.members or []) if getattr(m, 'id', None)]
    return {'id': team.id or '', 'name': team.name or team.id or '', 'members': members}


def _step_summary(step: AgnoStep) -> dict[str, Any]:
    parallel = getattr(step, 'steps', None) if type(step).__name__ == 'Parallel' else None
    if parallel is not None:
        return {'name': getattr(step, 'name', '') or 'Parallel', 'parallel': [_step_summary(s) for s in parallel]}
    agent = getattr(step, 'agent', None)
    hitl = bool(
        getattr(step, 'requires_output_review', False)
        or getattr(step, 'requires_confirmation', False)
        or getattr(step, 'requires_user_input', False),
    )
    return {'name': step.name or '', 'agent': getattr(agent, 'id', None) if agent else None, 'hitl': hitl}


def _workflow_summary(workflow: AgnoWorkflow) -> dict[str, Any]:
    return {
        'id': workflow.id or '',
        'name': workflow.name or workflow.id or '',
        'description': getattr(workflow, 'description', '') or '',
        'steps': [_step_summary(s) for s in (workflow.steps or [])],
    }


def _jinja_context(spec: Spec) -> dict[str, Any]:
    """Convert the Pydantic Spec to a plain dict for Jinja consumption.

    Agents / teams / workflows are agno-native (not Pydantic) so we summarise them by hand for templates that need `{id,
    name, steps, ...}`. The rest (org, ui, charter, env vars, setup, groups, documents) round-trips through
    `model_dump`. Templates that referenced the old `generated.foo` shape see a backwards-compatible namespace.
    """
    base = spec.model_dump(mode='json', exclude={'agents', 'teams', 'workflows'})
    base['year'] = datetime.now(tz=UTC).year
    base['generated'] = {
        'agents': [_agent_summary(a) for a in spec.agents],
        'teams': [_team_summary(t) for t in spec.teams],
        'workflows': [_workflow_summary(w) for w in spec.workflows],
        'agent_groups': base['agent_groups'],
        'workflow_groups': base['workflow_groups'],
        'ui': base['ui'],
        'charter': base['charter'],
        'state': base['state'],
        'documents': base['documents'],
    }
    return base


def render(spec_path: Path, output_dir: Path, template_dir: Path | None = None) -> None:
    """Render the project template from a spec file.

    Args:
        spec_path: Path to the user's `spec.py`.
        output_dir: Output directory (created/overwritten in place).
        template_dir: Override the template root (defaults to the agentorg-shipped template).
    """
    # Load specification
    spec = runpy.run_path(str(spec_path)).get('spec')
    if not isinstance(spec, Spec):
        msg = f'spec.py must define a top-level `spec` of type Spec, got {type(spec).__name__}.'
        raise TypeError(msg)

    data = _jinja_context(spec)

    if template_dir is None:
        template_dir = Path(str(files(__package__) / 'template'))

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(disabled_extensions=('jinja',), default=False),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=False,
    )
    env.policies['json.dumps_kwargs'] = {'ensure_ascii': False, 'sort_keys': True}

    for path in template_dir.rglob('*'):
        raw_relative_path = path.relative_to(template_dir).as_posix()
        rendered_path = env.from_string(raw_relative_path).render(**data)
        relative_path = rendered_path.removesuffix('.jinja')
        if relative_path and not relative_path.endswith('/'):
            output_path = Path(output_dir) / relative_path
            if path.is_dir():
                output_path.mkdir(exist_ok=True, parents=True)
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if rendered_path.endswith('.jinja'):
                    output_path.write_text(env.get_template(raw_relative_path).render(**data))
                else:
                    shutil.copy(path, output_path)

    # Drop the user's spec.py into the rendered project at <package>/spec.py so
    # the runtime can `from <package>.spec import spec` at boot.
    package_name = spec.org.package_name
    spec_dest = output_dir / 'src' / package_name / 'spec.py'
    spec_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(spec_path, spec_dest)
