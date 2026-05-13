"""Knowledge-tool round-trip tests — write -> read -> list against the local SQLite + Chroma store.

The embedder runs whenever a knowledge unit is written, so these tests require
`GOOGLE_API_KEY` to be set. With the env var missing the whole module skips.
"""

import pytest

from agentorg.core.tools.knowledge import (
    delete_knowledge,
    list_knowledge,
    read_knowledge,
    write_knowledge,
)
from agentorg.core.tools.tables import create_app_tables


@pytest.fixture(scope='module', autouse=True)
def _setup(needs_google_api: None) -> None:  # noqa: PT004
    """Embedder gate + ensure app tables exist (we don't import the app in this module)."""
    create_app_tables()


def test_write_then_read_round_trips() -> None:
    """`write_knowledge` persists a unit that `read_knowledge` returns verbatim."""
    write_knowledge(
        type='report',
        name='knowledge_roundtrip',
        title='Knowledge Round-trip',
        content='Hello from the test suite.',
        metadata={'source': 'pytest'},
    )
    text = read_knowledge(type='report', name='knowledge_roundtrip')
    assert 'Hello from the test suite.' in text


def test_list_filters_by_type() -> None:
    """`list_knowledge(type='report')` only returns rows of that type."""
    write_knowledge(type='report', name='listed_one', title='Listed One', content='c1')
    listing = list_knowledge(type='report')
    assert 'listed_one' in listing


def test_delete_removes_a_unit() -> None:
    """`delete_knowledge` removes a previously-written unit; subsequent listing doesn't show it."""
    write_knowledge(type='report', name='to_be_deleted', title='X', content='gone soon')
    delete_knowledge(type='report', name='to_be_deleted')
    listing = list_knowledge(type='report')
    assert 'to_be_deleted' not in listing
