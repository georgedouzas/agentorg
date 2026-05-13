"""Application tables shared across every agentorg-generated org.

Two tables: `knowledge` (everything an agent produces) and `org_state` (per-user charter parameters and operational
data). agno owns its own session / memory / learnings tables — those aren't managed here.

The DDL branches on `AGENTORG_INFRA`: SQLite types in local mode, Postgres types in docker.
"""

import contextlib
from os import getenv

from sqlalchemy import text

from agentorg.core.tools._engine import get_engine


def _is_docker() -> bool:
    return getenv('AGENTORG_INFRA', 'local').lower() == 'docker'


_KNOWLEDGE_POSTGRES = (
    'CREATE TABLE IF NOT EXISTS knowledge ('
    ' id            SERIAL       PRIMARY KEY,'
    ' type          VARCHAR(50)  NOT NULL,'
    ' name          VARCHAR(200) NOT NULL,'
    ' title         TEXT,'
    ' content       TEXT,'
    ' data          JSONB,'
    " metadata      JSONB        NOT NULL DEFAULT '{}',"
    ' created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),'
    ' updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),'
    ' UNIQUE (type, name)'
    ')'
)

_ORG_STATE_POSTGRES = (
    'CREATE TABLE IF NOT EXISTS org_state ('
    ' id          SERIAL       PRIMARY KEY,'
    " user_id     VARCHAR(100) NOT NULL UNIQUE DEFAULT 'default',"
    " parameters  JSONB        NOT NULL DEFAULT '{}',"
    " data        JSONB        NOT NULL DEFAULT '{}',"
    ' updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()'
    ')'
)

_KNOWLEDGE_SQLITE = (
    'CREATE TABLE IF NOT EXISTS knowledge ('
    ' id            INTEGER PRIMARY KEY AUTOINCREMENT,'
    ' type          TEXT    NOT NULL,'
    ' name          TEXT    NOT NULL,'
    ' title         TEXT,'
    ' content       TEXT,'
    ' data          TEXT,'
    " metadata      TEXT    NOT NULL DEFAULT '{}',"
    ' created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,'
    ' updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,'
    ' UNIQUE (type, name)'
    ')'
)

_ORG_STATE_SQLITE = (
    'CREATE TABLE IF NOT EXISTS org_state ('
    ' id          INTEGER PRIMARY KEY AUTOINCREMENT,'
    " user_id     TEXT    NOT NULL UNIQUE DEFAULT 'default',"
    " parameters  TEXT    NOT NULL DEFAULT '{}',"
    " data        TEXT    NOT NULL DEFAULT '{}',"
    ' updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP'
    ')'
)

_POSTGRES_DDL: list[str] = [
    _KNOWLEDGE_POSTGRES,
    'CREATE INDEX IF NOT EXISTS knowledge_type_idx     ON knowledge(type)',
    'CREATE INDEX IF NOT EXISTS knowledge_metadata_idx ON knowledge USING gin(metadata)',
    _ORG_STATE_POSTGRES,
]

_SQLITE_DDL: list[str] = [
    _KNOWLEDGE_SQLITE,
    'CREATE INDEX IF NOT EXISTS knowledge_type_idx ON knowledge(type)',
    _ORG_STATE_SQLITE,
]


def create_app_tables() -> None:
    """Create application tables.

    Run once at startup.
    """
    statements = _POSTGRES_DDL if _is_docker() else _SQLITE_DDL
    with get_engine().begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


_USER_DATA_TABLES = [
    'org_state',
    'knowledge',
    'team_knowledge_contents',
    'team_learnings_contents',
    'agno_sessions',
    'agno_memories',
    'agno_knowledge',
    'agno_learnings',
]


def truncate_user_data() -> None:
    """Wipe every table that holds user-created or per-user state."""
    wipe = 'TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE' if _is_docker() else 'DELETE FROM {tbl}'
    with get_engine().begin() as conn:
        for tbl in _USER_DATA_TABLES:
            with contextlib.suppress(Exception):
                conn.execute(text(wipe.format(tbl=tbl)))
