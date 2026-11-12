"""Tests for the tags module."""

from agentorg.core.agents.tools import read_knowledge, side_effect_of, tool, write_knowledge


def test_tool_sets_side_effect_outbound_and_tags() -> None:
    """The decorator records the side effect, the outbound flag and the tags on the function."""

    @tool('read', outbound=True, tags=('crm',))
    def lookup() -> str:
        """Look up."""
        return 'found'

    assert (lookup.side_effect, lookup.outbound, lookup.tags) == ('read', True, ['crm'])  # type: ignore[attr-defined]


def test_tool_defaults_to_write_without_tags() -> None:
    """A bare `tool()` marks the function as a non-outbound write with no tags."""

    @tool()
    async def send() -> str:
        """Send."""
        return 'sent'

    assert (send.side_effect, send.outbound, send.tags) == ('write', False, [])  # type: ignore[attr-defined]


def test_tool_returns_original_function() -> None:
    """The decorator returns the exact function it received."""

    async def lookup(x: int) -> int:
        """Look up."""
        return x

    assert tool('read')(lookup) is lookup


def test_side_effect_of_treats_undecorated_tool_as_write() -> None:
    """A tool without the decorator is governed as a write."""

    def plain() -> str:
        """Plain."""
        return 'plain'

    assert side_effect_of(plain) == 'write'


def test_side_effect_of_reads_builtin_knowledge_tools() -> None:
    """The shipped knowledge tools declare reads and writes correctly."""
    assert (side_effect_of(read_knowledge), side_effect_of(write_knowledge)) == ('read', 'write')
