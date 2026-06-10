"""Platform Engineer tools that introspect infra, env vars, and service health."""

import os
import socket

from agentorg.core.agents.tools._tags import tags


@tags('platform', 'infra')
def read_infra() -> str:
    """Report the current infra mode and data directory.

    Returns:
        config: The infra mode and data dir.
    """
    mode = os.getenv('AGENTORG_INFRA', 'local')
    data = os.getenv('AGENTORG_DATA_DIR', '.agentorg-data') if mode == 'local' else 'postgres'
    return f'infra={mode}\ndata={data}'


@tags('platform', 'infra')
def list_env_vars() -> str:
    """List all `AGENTORG_*` and `DB_*` env vars currently set."""
    lines = ['Env vars:']
    for name in sorted(os.environ):
        if name.startswith(('AGENTORG_', 'DB_', 'GOOGLE_', 'EXA_')):
            lines.append(f'  {name}=<set>')
    return '\n'.join(lines)


@tags('platform', 'infra')
def check_health(host: str = '127.0.0.1', port: int = 8000, timeout: float = 1.0) -> str:
    """Quick TCP check that the FastAPI app is listening."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return f'OK: {host}:{port} reachable.'
    except OSError as exc:
        return f'FAIL: {host}:{port} unreachable ({exc}).'
