"""Backend Engineer tools that introspect agent specs and run tests."""

import json
import subprocess
from pathlib import Path
from typing import Any

from agentorg.core.agents.tools import tags


@tags('platform', 'backend')
def list_agent_ids(spec_agents: list[dict[str, Any]] | None = None) -> str:
    """List every agent id in the spec.

    Arguments:
        spec_agents: Agent dicts from the spec, or None for an empty list.

    Returns:
        listing: The agent ids, one per line.
    """
    agents = spec_agents or []
    if not agents:
        return 'No agents in spec.'
    return 'Registered agents:\n' + '\n'.join(f"  - {a.get('id', '?')}" for a in agents)


@tags('platform', 'backend')
def read_agent_spec(agent_id: str, spec_agents: list[dict[str, Any]] | None = None) -> str:
    """Return the agent's spec entry as pretty-printed JSON.

    Arguments:
        agent_id: The agent id to look up.
        spec_agents: Agent dicts from the spec, or None for an empty list.

    Returns:
        json: The agent's spec entry, or a not-found message.
    """
    for agent in spec_agents or []:
        if agent.get('id') == agent_id:
            return json.dumps(agent, indent=2)
    return f"No such agent: {agent_id!r}."


@tags('platform', 'backend', 'qa')
def run_tests(cwd: str = '.') -> str:
    """Run `uv run pytest` in `cwd`.

    Arguments:
        cwd: The directory to run pytest from.

    Returns:
        summary: A one-line pytest summary.
    """
    result = subprocess.run(
        ['uv', 'run', 'pytest', '-x', '--tb=line', '-q'],  # noqa: S607
        capture_output=True,
        text=True,
        cwd=str(Path(cwd).resolve()),
        check=False,
    )
    last = (result.stdout + result.stderr).strip().splitlines()[-1] if result.stdout or result.stderr else ''
    return f'exit={result.returncode}  {last}'
