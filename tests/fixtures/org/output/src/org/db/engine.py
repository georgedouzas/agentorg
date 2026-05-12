"""Singleton SQLAlchemy engine shared across the application."""

from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine

from org.db.url import db_path


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the shared SQLAlchemy engine, creating it on first call."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}")