"""Knowledge-tool round-trip tests — write -> read -> list -> delete against AgentField memory.

The knowledge tools resolve the running node via `Agent.get_current()` and store into its global-scope memory, which
needs a control plane — so these tests take `needs_memory` (skipped when `AGENTFIELD_SERVER` is unset) and the `node`
fixture (which patches `Agent.get_current()` to the rendered node).
"""

import uuid

import pytest

from agentorg.core.tools.knowledge import (
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
    await write_knowledge(type='report', name=name, title='Round-trip', content='Hello from the test suite.')
    text = await read_knowledge(type='report', name=name)
    assert 'Hello from the test suite.' in text


@pytest.mark.asyncio
async def test_list_filters_by_type() -> None:
    """`list_knowledge(type='report')` surfaces a written report."""
    name = f'listed_{uuid.uuid4().hex[:8]}'
    await write_knowledge(type='report', name=name, title='Listed', content='c1')
    listing = await list_knowledge(type='report')
    assert name in listing


@pytest.mark.asyncio
async def test_delete_removes_a_unit() -> None:
    """`delete_knowledge` removes a unit; subsequent listing doesn't show it."""
    name = f'gone_{uuid.uuid4().hex[:8]}'
    await write_knowledge(type='report', name=name, title='X', content='gone soon')
    await delete_knowledge(type='report', name=name)
    listing = await list_knowledge(type='report')
    assert name not in listing
