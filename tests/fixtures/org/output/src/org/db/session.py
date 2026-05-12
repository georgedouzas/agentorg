"""Local-mode database connection helpers — SQLite for sessions/contents, Chroma for vectors."""

from pathlib import Path

from agno.db.sqlite import SqliteDb
from agno.knowledge import Knowledge
from agno.knowledge.embedder.google import GeminiEmbedder
from agno.vectordb.chroma import ChromaDb

from org.db.url import db_path, vector_path

DB_ID = "org-db"


def get_postgres_db(contents_table: str | None = None) -> SqliteDb:
    """Create a SqliteDb instance.

    Args:
        contents_table: Optional table name for storing knowledge contents.

    Returns:
        Configured SqliteDb instance.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    if contents_table is not None:
        return SqliteDb(id=DB_ID, db_file=db_path, knowledge_table=contents_table)
    return SqliteDb(id=DB_ID, db_file=db_path)


def create_knowledge(name: str, table_name: str) -> Knowledge:
    """Create a Knowledge instance with Chroma vector search.

    Args:
        name: Display name for the knowledge base.
        table_name: Vector collection name.

    Returns:
        Configured Knowledge instance.
    """
    Path(vector_path).mkdir(parents=True, exist_ok=True)
    return Knowledge(
        name=name,
        vector_db=ChromaDb(
            collection=table_name,
            path=vector_path,
            persistent_client=True,
            embedder=GeminiEmbedder(id="gemini-embedding-001"),
        ),
        contents_db=get_postgres_db(contents_table=f"{table_name}_contents"),
    )