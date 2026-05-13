"""Platform-engineer tools — introspect infra, env vars, and service health."""

import os
import socket

from ._spec import load_config


def read_infra() -> str:
    """Report the current infra configuration: mode, DB, embedder."""
    cfg = load_config()
    parts = [
        f"app:    {cfg.get('ui', {}).get('app', {}).get('name', 'unknown')}",
        f"agents: {len(cfg.get('agents') or {})} registered",
        f"teams:  {len(cfg.get('teams') or [])} declared",
        f"flows:  {len(cfg.get('workflows') or [])} declared",
    ]
    return "\n".join(parts)


def list_env_vars() -> str:
    """List required + optional env vars from the spec's `setup` section, plus whether each is currently set."""
    cfg = load_config()
    setup = cfg.get("setup") or {}
    steps = setup.get("steps") or []
    lines: list[str] = []
    seen: set[str] = set()
    for step in steps:
        for var in step.get("vars", []) or []:
            if var in seen:
                continue
            seen.add(var)
            present = "set" if os.getenv(var) else "MISSING"
            lines.append(f"  {var:24s} [{present}]")
    return "Env vars from setup steps:\n" + "\n".join(lines) if lines else "No env vars declared in setup."


def check_health(host: str = "127.0.0.1", port: int = 8000, timeout: float = 1.0) -> str:
    """Quick TCP check that the FastAPI app is listening on the given host/port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return f"OK: {host}:{port} reachable."
    except OSError as exc:
        return f"FAIL: {host}:{port} unreachable ({exc})."
