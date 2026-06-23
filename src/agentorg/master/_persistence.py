"""Disk persistence for the master agent's interview draft."""

import json
from pathlib import Path

from ..core.spec import Spec
from ._models import AgentSpec, CustomTool, TeamSpec, WorkflowSpec
from ._state import Discovery, Stage, State, get_state

DEFAULT_DRAFT_PATH = Path.home() / '.agentorg' / 'draft.json'


def save_draft(path: Path = DEFAULT_DRAFT_PATH) -> Path:
    """Snapshot the current `State` to `path` as JSON.

    Arguments:
        path: Destination file. Parents are created if missing.

    Returns:
        path: The path written (same as the argument).
    """
    state = get_state()
    payload: dict[str, object] = {
        'spec': state.spec.model_dump(mode='json'),
        'custom_tools': [t.model_dump(mode='json') for t in state.custom_tools],
        'stage': state.stage,
    }
    if state.discovery is not None:
        payload['discovery'] = {
            'what_the_group_does': state.discovery.what_the_group_does,
            'who_serves': state.discovery.who_serves,
            'concrete_tasks_owned': state.discovery.concrete_tasks_owned,
            'typical_flow': state.discovery.typical_flow,
            'business_context': state.discovery.business_context,
            'current_pain_or_alternative': state.discovery.current_pain_or_alternative,
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def load_draft(path: Path = DEFAULT_DRAFT_PATH) -> State:
    """Replace the singleton state with the contents of `path`.

    Arguments:
        path: JSON draft file to load.

    Returns:
        state: The updated singleton state.

    Raises:
        FileNotFoundError: If `path` does not exist.
    """
    data = json.loads(Path(path).read_text())
    spec_data = data['spec']
    # AI.agents / teams / workflows lose their concrete Pydantic types on dump (typed as list[Any]).
    # Re-construct them explicitly so they keep their attributes.
    spec_data['ai']['agents'] = [_revive(a, AgentSpec) for a in spec_data['ai']['agents']]
    spec_data['ai']['teams'] = [_revive(t, TeamSpec) for t in spec_data['ai']['teams']]
    spec_data['ai']['workflows'] = [_revive(w, WorkflowSpec) for w in spec_data['ai']['workflows']]
    spec = Spec(**spec_data)
    state = get_state()
    state.spec = spec
    state.custom_tools = [CustomTool(**t) for t in data.get('custom_tools', [])]
    valid_stages: tuple[Stage, ...] = ('discover', 'configure', 'build', 'refine', 'handoff')
    legacy_migration: dict[str, Stage] = {'generate': 'build'}
    raw_stage = data.get('stage', 'discover')
    migrated = legacy_migration.get(raw_stage, raw_stage)
    state.stage = migrated if migrated in valid_stages else 'discover'
    discovery_data = data.get('discovery')
    if isinstance(discovery_data, dict):
        state.discovery = Discovery(
            what_the_group_does=str(discovery_data.get('what_the_group_does', '')),
            who_serves=str(discovery_data.get('who_serves', '')),
            concrete_tasks_owned=str(discovery_data.get('concrete_tasks_owned', '')),
            typical_flow=str(discovery_data.get('typical_flow', '')),
            business_context=str(discovery_data.get('business_context', '')),
            current_pain_or_alternative=str(discovery_data.get('current_pain_or_alternative', '')),
        )
    else:
        state.discovery = None
    return state


def _revive(item: object, target_cls: type) -> object:
    """Re-instantiate a Pydantic model from a dict; pass non-dicts through unchanged."""
    if isinstance(item, dict):
        return target_cls(**item)
    return item
