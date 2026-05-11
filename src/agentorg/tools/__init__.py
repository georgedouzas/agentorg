"""Runtime helpers shared by every agentorg-generated org.

Spec wrappers (in each org's ``config/tools/``) and the rendered agent / workflow factories import from this package
directly. The engine, agno ``PostgresDb``, and agno ``Knowledge`` instances are built from standard env vars
(``DB_HOST`` / ``DB_PORT`` / ``DB_USER`` / ``DB_PASS`` / ``DB_DATABASE``), so no bind step is needed at startup — the
first call materialises the resource, subsequent calls hit the ``functools.lru_cache``.
"""

from ._engine import get_engine, get_postgres_db, get_team_knowledge

__all__ = [
    "get_engine",
    "get_postgres_db",
    "get_team_knowledge",
]
