"""Universal application tables: knowledge and org_state.

`knowledge` holds any agent-produced unit of knowledge — text artifacts (research, memo, report),
structured data (charts, stats, tables), or a refresh recipe (provider + args + schedule) that
the scheduler periodically re-evaluates. Static rows have a NULL provider; live rows refresh.

`org_state` holds per-user structured org state (charter parameters + operational data).

Learnings live in agno's own `team_learnings_contents` table — managed by LearningMachine.
"""

from sqlalchemy import text

from eng_team.db.engine import get_engine

# Migrate any pre-existing `documents` table to `knowledge` before creating fresh.
_MIGRATE = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents')
     AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'knowledge') THEN
    ALTER TABLE documents RENAME TO knowledge;
  END IF;
END $$;
"""

_SQL = """
CREATE TABLE IF NOT EXISTS knowledge (
    id            SERIAL       PRIMARY KEY,
    type          VARCHAR(50)  NOT NULL,
    name          VARCHAR(200) NOT NULL,
    title         TEXT,
    content       TEXT,
    data          JSONB,
    display       JSONB,
    provider      TEXT,
    args          JSONB,
    schedule      TEXT,
    last_computed TIMESTAMPTZ,
    last_error    TEXT,
    metadata      JSONB        NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (type, name)
);

ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS title         TEXT;
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS data          JSONB;
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS display       JSONB;
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS provider      TEXT;
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS args          JSONB;
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS schedule      TEXT;
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS last_computed TIMESTAMPTZ;
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS last_error    TEXT;
ALTER TABLE knowledge ALTER COLUMN content DROP NOT NULL;

CREATE INDEX IF NOT EXISTS knowledge_type_idx     ON knowledge(type);
CREATE INDEX IF NOT EXISTS knowledge_metadata_idx ON knowledge USING gin(metadata);
CREATE INDEX IF NOT EXISTS knowledge_schedule_idx ON knowledge(schedule) WHERE schedule IS NOT NULL;

CREATE TABLE IF NOT EXISTS org_state (
    id          SERIAL       PRIMARY KEY,
    user_id     VARCHAR(100) NOT NULL UNIQUE DEFAULT 'default',
    parameters  JSONB        NOT NULL DEFAULT '{}',
    data        JSONB        NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
"""


def create_app_tables() -> None:
    """Create application tables. Run once at startup. Migrates legacy `documents` table."""
    with get_engine().begin() as conn:
        conn.execute(text(_MIGRATE))
        conn.execute(text(_SQL))


_USER_DATA_TABLES = [
    "org_state",
    "knowledge",
    "team_knowledge_contents",
    "team_learnings_contents",
    "agno_sessions",
    "agno_memories",
    "agno_knowledge",
    "agno_learnings",
]


def truncate_user_data() -> None:
    """Wipe every table that holds user-created or per-user state. Use only when
    `RESET_ON_STARTUP=1`. Static seed data (policy, platform_reference, overview feeds)
    is re-created by the seeders that run after this in main.py."""
    with get_engine().begin() as conn:
        for tbl in _USER_DATA_TABLES:
            try:
                conn.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
            except Exception:  # noqa: BLE001, S110
                # Table may not exist yet on a fresh install — fine.
                pass
