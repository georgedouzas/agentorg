"""Local-mode file paths for the SQLite session DB and the Chroma vector store."""

from os import getenv
from pathlib import Path

_DATA_DIR = Path(getenv("AGENTORG_DATA_DIR", ".agentorg-data"))

db_path = str(_DATA_DIR / "org.db")
vector_path = str(_DATA_DIR / "chroma")