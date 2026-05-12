"""Backend-engineer tools — introspect agent specs and run tests."""

import json
import subprocess

from ._spec import load_config, project_root


def list_agent_ids() -> str:
    """List every agent id registered in `config.yaml`."""
    agents = load_config().get("agents") or {}
    return "Registered agents:\n" + "\n".join(f"  - {aid}" for aid in sorted(agents))


def read_agent_spec(agent_id: str) -> str:
    """Return the agent's full spec block from `config.yaml` as pretty-printed JSON."""
    agents = load_config().get("agents") or {}
    if agent_id not in agents:
        return f"No such agent: {agent_id!r}. Use `list_agent_ids` to see registered agents."
    return json.dumps(agents[agent_id], indent=2)


def run_tests() -> str:
    """Run the project's pytest suite.

    Returns a short summary line.
    """
    result = subprocess.run(
        ["uv", "run", "pytest", "-x", "--tb=line", "-q"],  # noqa: S607
        capture_output=True,
        text=True,
        cwd=str(project_root()),
        check=False,
    )
    last = (result.stdout + result.stderr).strip().splitlines()[-1] if result.stdout or result.stderr else ""
    return f"exit={result.returncode}  {last}"
