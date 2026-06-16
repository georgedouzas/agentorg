"""Disk persistence for the master agent's interview draft.

Drafts live under `~/.agentorg/draft.json` by default. Each save snapshots the working `Spec` plus
any custom-tool definitions; the loader reconstructs `AgentSpec` / `TeamSpec` / `WorkflowSpec` from
the JSON because `AI.agents` is `list[Any]` and otherwise loses its types on round-trip.
"""

import json
from pathlib import Path

from agentorg.core.spec import Spec

from ._models import AgentSpec, CustomTool, TeamSpec, WorkflowSpec
from ._state import State, get_state

DEFAULT_DRAFT_PATH = Path.home() / '.agentorg' / 'draft.json'


def save_draft(path: Path = DEFAULT_DRAFT_PATH) -> Path:
    """Snapshot the current `State` to `path` as JSON.

    Arguments:
        path: Destination file. Parents are created if missing.

    Returns:
        path: The path written (same as the argument).
    """
    state = get_state()
    payload = {
        'spec': state.spec.model_dump(mode='json'),
        'custom_tools': [t.model_dump(mode='json') for t in state.custom_tools],
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
    return state


def _revive(item: object, target_cls: type) -> object:
    """Re-instantiate a Pydantic model from a dict; pass non-dicts through unchanged."""
    if isinstance(item, dict):
        return target_cls(**item)
    return item
