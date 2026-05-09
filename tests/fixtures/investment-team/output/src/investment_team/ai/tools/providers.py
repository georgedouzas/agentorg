"""Provider registry — bounded vocabulary of refresh sources for live knowledge.

A provider is a typed Python function (decorated with `@provider`) that an agent can invoke by name through a
`knowledge` row. The registry is the security boundary: agents can only compose pre-registered functions with typed
args. No `eval`, no arbitrary code.

Universal providers ship with agentorg infra. Per-org providers can be registered by importing additional modules at app
startup.
"""

from collections.abc import Callable
from typing import Any

PROVIDERS: dict[str, dict[str, Any]] = {}


def provider(name: str, args: dict[str, type] | None = None) -> Callable:
    """Decorator: register a function as a refresh provider under `name`."""

    def deco(fn: Callable) -> Callable:
        PROVIDERS[name] = {"fn": fn, "args": args or {}, "doc": fn.__doc__ or ""}
        return fn
    return deco


def get_provider(name: str) -> Callable:
    """Look up a provider function by registered name."""
    if name not in PROVIDERS:
        msg = f"Unknown provider: {name!r}"
        raise ValueError(msg)
    return PROVIDERS[name]["fn"]


def list_providers() -> str:
    """List all registered providers with their arg schemas.

    Agents call this to discover what data sources they can register a knowledge row against.
    """
    if not PROVIDERS:
        return "No providers registered."
    lines = ["Available providers:"]
    for name, meta in sorted(PROVIDERS.items()):
        args = meta["args"]
        sig = ", ".join(f"{k}: {v.__name__ if hasattr(v, '__name__') else v}" for k, v in args.items())
        lines.append(f"  - {name}({sig})")
        doc = meta["doc"].strip().split("\n")[0] if meta["doc"] else ""
        if doc:
            lines.append(f"    {doc}")
    return "\n".join(lines)


def import_universal_providers() -> None:
    """Import side-effect-only modules so their @provider decorators run at app startup.

    Universal providers (yfinance, state, knowledge) ship with agentorg infra. Per-org providers live in modules
    prefixed with `_providers_` in this directory and are auto-discovered here.
    """
    import importlib  # noqa: PLC0415
    import pkgutil  # noqa: PLC0415

    from investment_team.ai import tools  # noqa: PLC0415

    for _, mod_name, _ in pkgutil.iter_modules(tools.__path__):
        if mod_name.startswith("_providers_"):
            importlib.import_module(f"{tools.__name__}.{mod_name}")
