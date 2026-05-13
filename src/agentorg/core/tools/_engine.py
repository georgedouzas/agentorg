"""DB engine + shared Knowledge factories.

Backend chosen via the `AGENTORG_INFRA` env var:
  - `local` (default): SQLite for sessions, Chroma for vectors, both file-backed under
    `AGENTORG_DATA_DIR` (defaults to `./.agentorg-data`).
  - `docker`: PostgreSQL via `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASS` / `DB_DATABASE`,
    pgvector for the vector store.

Every factory is `functools.lru_cache`-d so each (name, table) pair yields exactly one
instance per process.
"""

from functools import lru_cache
from os import getenv
from pathlib import Path
from urllib.parse import quote

from agno.db.postgres import PostgresDb
from agno.db.sqlite import SqliteDb
from agno.knowledge import Knowledge
from agno.knowledge.embedder.google import GeminiEmbedder
from agno.vectordb.chroma import ChromaDb
from agno.vectordb.pgvector import PgVector, SearchType
from sqlalchemy import Engine, create_engine


def _infra() -> str:
    return getenv('AGENTORG_INFRA', 'local').lower()


def _data_dir() -> Path:
    d = Path(getenv('AGENTORG_DATA_DIR', '.agentorg-data'))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _postgres_url() -> str:
    driver = getenv('DB_DRIVER', 'postgresql+psycopg')
    user = getenv('DB_USER', 'ai')
    password = quote(getenv('DB_PASS', 'ai'), safe='')
    host = getenv('DB_HOST', 'localhost')
    port = getenv('DB_PORT', '5432')
    database = getenv('DB_DATABASE', 'ai')
    return f'{driver}://{user}:{password}@{host}:{port}/{database}'


def _sqlite_path() -> str:
    slug = getenv('AGENTORG_ORG_SLUG', 'org')
    return str(_data_dir() / f'{slug}.db')


def _chroma_path() -> str:
    return str(_data_dir() / 'chroma')


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the shared SQLAlchemy engine for the current `AGENTORG_INFRA`."""
    if _infra() == 'docker':
        return create_engine(_postgres_url(), pool_pre_ping=True)
    return create_engine(f'sqlite:///{_sqlite_path()}')


@lru_cache(maxsize=4)
def get_postgres_db(contents_table: str | None = None) -> PostgresDb | SqliteDb:
    """Return the shared agno session DB (PostgresDb in docker, SqliteDb in local)."""
    db_id = getenv('AGENTORG_ORG_SLUG', 'org') + '-db'
    if _infra() == 'docker':
        if contents_table is not None:
            return PostgresDb(id=db_id, db_url=_postgres_url(), knowledge_table=contents_table)
        return PostgresDb(id=db_id, db_url=_postgres_url())
    if contents_table is not None:
        return SqliteDb(id=db_id, db_file=_sqlite_path(), knowledge_table=contents_table)
    return SqliteDb(id=db_id, db_file=_sqlite_path())


@lru_cache(maxsize=8)
def create_knowledge(name: str, table_name: str) -> Knowledge:
    """Return the shared agno Knowledge instance for (name, table).

    Embedder is GeminiEmbedder.
    """
    embedder = GeminiEmbedder(id='gemini-embedding-001')
    if _infra() == 'docker':
        vector_db: PgVector | ChromaDb = PgVector(
            db_url=_postgres_url(),
            table_name=table_name,
            search_type=SearchType.hybrid,
            embedder=embedder,
        )
    else:
        vector_db = ChromaDb(
            collection=table_name,
            path=_chroma_path(),
            persistent_client=True,
            embedder=embedder,
        )
    return Knowledge(
        name=name,
        vector_db=vector_db,
        contents_db=get_postgres_db(contents_table=f'{table_name}_contents'),
    )
