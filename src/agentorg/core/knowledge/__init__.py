"""Knowledge domain: pure scope ops plus agent-callable wrappers."""

from agentorg.core.knowledge._base import PREFIX, embed, key, list_units, similarity_units
from agentorg.core.knowledge._tools import (
    delete_knowledge,
    list_knowledge,
    read_knowledge,
    search_knowledge,
    write_knowledge,
)

__all__ = [
    'PREFIX',
    'delete_knowledge',
    'embed',
    'key',
    'list_knowledge',
    'list_units',
    'read_knowledge',
    'search_knowledge',
    'similarity_units',
    'write_knowledge',
]
