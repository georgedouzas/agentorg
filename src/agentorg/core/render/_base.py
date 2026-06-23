"""Render an organization from a single `spec.py` file."""

import runpy
import shutil
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agentorg.core.spec import Spec


def _runnable_name(obj: object) -> str:
    """Best-effort stable name for a runnable: `.id`, then `.name`, then `.__name__`."""
    name = getattr(obj, 'id', None) or getattr(obj, 'name', None) or getattr(obj, '__name__', None)
    return str(name) if name else ''


def _file_matches_text(path: Path, content: str) -> bool:
    """True if `path` already exists with text equal to `content`."""
    try:
        return path.read_text() == content
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return False


def _file_matches_bytes(dest: Path, source: Path) -> bool:
    """True if `dest` already exists with bytes equal to `source`."""
    try:
        return dest.read_bytes() == source.read_bytes()
    except (FileNotFoundError, OSError):
        return False


def _agent_summary(agent: object) -> dict[str, Any]:
    name = _runnable_name(agent)
    return {'id': name, 'name': getattr(agent, 'name', None) or name, 'role': getattr(agent, 'role', '') or ''}


def _team_summary(team: object) -> dict[str, Any]:
    members = [_runnable_name(m) for m in (getattr(team, 'members', None) or []) if _runnable_name(m)]
    name = _runnable_name(team)
    return {'id': name, 'name': getattr(team, 'name', None) or name, 'members': members}


def _step_summary(step: object) -> dict[str, Any]:
    parallel = getattr(step, 'steps', None) if type(step).__name__ == 'Parallel' else None
    if parallel is not None:
        return {'name': getattr(step, 'name', '') or 'Parallel', 'parallel': [_step_summary(s) for s in parallel]}
    agent = getattr(step, 'agent', None)
    hitl = bool(
        getattr(step, 'requires_output_review', False)
        or getattr(step, 'requires_confirmation', False)
        or getattr(step, 'requires_user_input', False),
    )
    return {
        'name': getattr(step, 'name', '') or '',
        'agent': _runnable_name(agent) if agent is not None else None,
        'hitl': hitl,
    }


def _workflow_summary(workflow: object) -> dict[str, Any]:
    name = _runnable_name(workflow)
    return {
        'id': name,
        'name': getattr(workflow, 'name', None) or name,
        'description': getattr(workflow, 'description', '') or '',
        'steps': [_step_summary(s) for s in (getattr(workflow, 'steps', None) or [])],
    }


def _jinja_context(spec: Spec) -> dict[str, Any]:
    """Convert the Pydantic Spec to a plain dict for Jinja consumption.

    Agents / teams / workflows are agno-native (not Pydantic) so we summarise them by hand for templates that need `{id,
    name, steps, ...}`. The rest (org, ui, principles, env vars, setup, groups, documents) round-trips through
    `model_dump`. Templates that referenced the old `generated.foo` shape see a backwards-compatible namespace.
    """
    base = spec.model_dump(mode='json', exclude={'ai'})
    base['year'] = datetime.now(tz=UTC).year
    base['generated'] = {
        'agents': [_agent_summary(a) for a in spec.ai.agents],
        'teams': [_team_summary(t) for t in spec.ai.teams],
        'workflows': [_workflow_summary(w) for w in spec.ai.workflows],
        'agent_groups': base['ui']['agent_groups'],
        'workflow_groups': base['ui']['workflow_groups'],
        'ui': base['ui'],
        'knowledge': base['knowledge'],
    }
    return base


def render(
    spec_path: Path,
    output_dir: Path,
    template_dir: Path | None = None,
    *,
    template: str = 'full',
) -> None:
    """Render a project from a spec file using one of the shipped templates.

    Arguments:
        spec_path: Path to the user's `spec.py`.
        output_dir: Output directory, created or overwritten in place.
        template_dir: Override the template root entirely (skips `template` selection).
        template: Which shipped template to use - `full` (default), `frontend`, `backend`,
            or `ai`. The partials produce runnable mini-projects scoped to one layer of
            the org (the React dashboard, the FastAPI service, or the agent definitions
            + a sandbox driver) for fast smoke / unit tests against that layer alone.
    """
    # Load specification
    spec = runpy.run_path(str(spec_path)).get('spec')
    if not isinstance(spec, Spec):
        msg = f'spec.py must define a top-level `spec` of type Spec, got {type(spec).__name__}.'
        raise TypeError(msg)

    data = _jinja_context(spec)

    if template_dir is None:
        template_dir = Path(str(files(__package__) / 'templates' / template))

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
                # Skip the write when the file already matches. Live preview re-renders
                # the whole tree on every chat turn; idempotent writes avoid touching
                # files whose content didn't actually change. Without this Vite's file
                # watcher fires for every template-derived file on every turn (hundreds
                # of events) and the dev server eventually crashes mid-interview.
                if rendered_path.endswith('.jinja'):
                    new_content = env.get_template(raw_relative_path).render(**data)
                    if not _file_matches_text(output_path, new_content):
                        output_path.write_text(new_content)
                elif not _file_matches_bytes(output_path, path):
                    shutil.copy(path, output_path)

    # Drop the user's spec.py into the rendered project at <package>/spec.py so
    # the runtime can `from <package>.spec import spec` at boot. Idempotent so the
    # live preview's rerender loop doesn't touch the file on no-op turns.
    package_name = spec.org.package_name
    spec_dest = output_dir / 'src' / package_name / 'spec.py'
    spec_dest.parent.mkdir(parents=True, exist_ok=True)
    if not _file_matches_bytes(spec_dest, spec_path):
        shutil.copyfile(spec_path, spec_dest)
