"""DB engine + shared Knowledge factories — built from standard env vars.

Every rendered agentorg project standardises on the same env-var convention (``DB_HOST`` / ``DB_PORT`` / ``DB_USER`` /
``DB_PASS`` / ``DB_DATABASE``), so the runtime helpers in ``agentorg.tools`` build their engine and shared Knowledge
instances directly from those vars. No bind step, no global mutable state — just ``functools.lru_cache`` over factory
functions so each (name, table) pair yields exactly one instance per process.
"""

from functools import lru_cache
from os import getenv
from urllib.parse import quote

from agno.db.postgres import PostgresDb
from agno.knowledge import Knowledge
from agno.knowledge.embedder.google import GeminiEmbedder
from agno.vectordb.pgvector import PgVector, SearchType
from sqlalchemy import Engine, create_engine


def _db_url() -> str:
    driver = getenv("DB_DRIVER", "postgresql+psycopg")
    user = getenv("DB_USER", "ai")
    password = quote(getenv("DB_PASS", "ai"), safe="")
    host = getenv("DB_HOST", "localhost")
    port = getenv("DB_PORT", "5432")
    database = getenv("DB_DATABASE", "ai")
    return f"{driver}://{user}:{password}@{host}:{port}/{database}"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Singleton SQLAlchemy engine for the current process."""
    return create_engine(_db_url(), pool_pre_ping=True)


@lru_cache(maxsize=4)
def get_postgres_db(contents_table: str | None = None, db_id: str = "agentorg-db") -> PostgresDb:
    """Shared agno ``PostgresDb`` instance, optionally bound to a contents table."""
    if contents_table is not None:
        return PostgresDb(id=db_id, db_url=_db_url(), knowledge_table=contents_table)
    return PostgresDb(id=db_id, db_url=_db_url())


@lru_cache(maxsize=4)
def get_team_knowledge(name: str, table_name: str) -> Knowledge:
    """Shared agno ``Knowledge`` instance for a given (display name, vector table)."""
    return Knowledge(
        name=name,
        vector_db=PgVector(
            db_url=_db_url(),
            table_name=table_name,
            search_type=SearchType.hybrid,
            embedder=GeminiEmbedder(id="gemini-embedding-001"),
        ),
        contents_db=get_postgres_db(contents_table=f"{table_name}_contents", db_id=f"{table_name}-db"),
    )
