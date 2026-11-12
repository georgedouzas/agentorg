"""Disk persistence for the master agent's interview draft."""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..core.spec import AI, Agent, Spec
from ._models import CustomSkill, CustomTool, UnitDraft
from ._sandbox import compile_tool
from ._state import Discovery, Stage, State, get_state
from ._structure import assemble_ai

DEFAULT_DRAFT_PATH = Path.home() / '.agentorg' / 'draft.json'
STAGES: tuple[Stage, ...] = ('discover', 'configure', 'build', 'refine', 'handoff')


def _agent_data(agent: Agent) -> dict[str, Any]:
    """Return an agent as JSON with its tools by name."""
    data = agent.model_dump(mode='json', exclude={'tools'}, exclude_unset=True)
    data['tools'] = [fn.__name__ for fn in agent.tools]
    return data


def save_draft(path: Path = DEFAULT_DRAFT_PATH) -> Path:
    """Snapshot the current `State` to `path` as JSON.

    Arguments:
        path: Destination file. Parents are created if missing.

    Returns:
        path: The path written (same as the argument).
    """
    state = get_state()
    payload: dict[str, object] = {
        'spec': state.spec.model_dump(mode='json', exclude={'ai'}, exclude_unset=True),
        'agents': [_agent_data(agent) for agent in state.agents],
        'units': [unit.model_dump(mode='json') for unit in state.units],
        'custom_tools': [tool.model_dump(mode='json') for tool in state.custom_tools],
        'custom_skills': [skill.model_dump(mode='json') for skill in state.custom_skills],
        'stage': state.stage,
    }
    if state.discovery is not None:
        payload['discovery'] = vars(state.discovery)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def load_draft(path: Path = DEFAULT_DRAFT_PATH) -> State:
    """Replace the singleton state with the contents of `path`.

    Arguments:
        path: JSON draft file to load.

    Returns:
        state: The updated singleton state.
    """
    data = json.loads(Path(path).read_text())
    state = get_state()
    state.custom_tools = [CustomTool(**tool) for tool in data.get('custom_tools', [])]
    state.custom_skills = [CustomSkill(**skill) for skill in data.get('custom_skills', [])]
    state.functions = {tool.name: compile_tool(tool.name, tool.source) for tool in state.custom_tools}
    state.agents = [
        Agent.model_validate({**agent, 'tools': [state.functions[name] for name in agent.get('tools', [])]})
        for agent in data.get('agents', [])
    ]
    state.units = [UnitDraft(**unit) for unit in data.get('units', [])]
    try:
        ai = assemble_ai(state.agents, state.units)
        state.structure_error = None
    except (ValidationError, ValueError) as error:
        ai, state.structure_error = AI(agents=[]), str(error)
    state.spec = Spec(**{**data['spec'], 'ai': ai})
    stage = data.get('stage', 'discover')
    state.stage = stage if stage in STAGES else 'discover'
    discovery = data.get('discovery')
    state.discovery = Discovery(**{k: str(v) for k, v in discovery.items()}) if isinstance(discovery, dict) else None
    return state
