"""Round-trip tests for the knowledge tools against AgentField memory."""

import uuid

import pytest

from agentorg.core.agents.tools import (
    delete_knowledge,
    list_knowledge,
    read_knowledge,
    write_knowledge,
)

pytestmark = pytest.mark.usefixtures('needs_memory', 'node')


@pytest.mark.asyncio
async def test_write_then_read_round_trips() -> None:
    """`write_knowledge` persists a unit that `read_knowledge` returns verbatim."""
    name = f'roundtrip_{uuid.uuid4().hex[:8]}'
    await write_knowledge(knowledge_type='report', name=name, title='Round-trip', content='Hello from the test suite.')
    text = await read_knowledge(knowledge_type='report', name=name)
    assert 'Hello from the test suite.' in text


@pytest.mark.asyncio
async def test_list_filters_by_type() -> None:
    """`list_knowledge(knowledge_type='report')` surfaces a written report."""
    name = f'listed_{uuid.uuid4().hex[:8]}'
    await write_knowledge(knowledge_type='report', name=name, title='Listed', content='c1')
    listing = await list_knowledge(knowledge_type='report')
    assert name in listing


@pytest.mark.asyncio
async def test_delete_removes_a_unit() -> None:
    """`delete_knowledge` removes a unit; subsequent listing doesn't show it."""
    name = f'gone_{uuid.uuid4().hex[:8]}'
    await write_knowledge(knowledge_type='report', name=name, title='X', content='gone soon')
    await delete_knowledge(knowledge_type='report', name=name)
    listing = await list_knowledge(knowledge_type='report')
    assert name not in listing
