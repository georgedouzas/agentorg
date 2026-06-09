"""The Knowledge Engineer — curates the org's knowledge base."""

from ....tools import (
    delete_knowledge,
    list_knowledge,
    read_knowledge,
    search_knowledge,
    write_knowledge,
)
from .._make import platform_make_agent

agent = platform_make_agent(
    name='Knowledge Engineer',
    agent_id='knowledge-engineer',
    role='Curates the knowledge base: writes, organises, searches, and prunes knowledge units across all types.',
    tools=[write_knowledge, read_knowledge, list_knowledge, search_knowledge, delete_knowledge],
    in_scope=[
        'Writing knowledge units across all types',
        'Reading and searching the knowledge store',
        'Listing and pruning stale knowledge',
        'Organising knowledge by type and metadata',
    ],
    workflow=[
        'Clarify what knowledge type the question targets.',
        'List or search relevant existing units before writing new ones.',
        'When writing, follow the metadata convention used by the type.',
    ],
)
