"""Tests for the tags module."""

import pytest

from agentorg.core.agents.tools import tags


@pytest.mark.parametrize(
    "tags_vals",
    [
        ['tag1', 'tag2'],
        ['tag2', 'tag1'],
    ],
)
def test_tags_decorator(tags_vals):
    """Test that the tags decorator correctly attaches tags to a tool."""

    @tags(*tags_vals)
    def tool():
        pass

    assert tool.tags == tags_vals


@pytest.mark.parametrize(
    "tags_vals",
    [
        ['tag1', 'tag2'],
        ['tag2', 'tag1'],
    ],
)
def test_tags_decorator_async(tags_vals):
    """Test that the tags decorator correctly attaches tags to an async tool."""

    @tags(*tags_vals)
    async def tool():
        pass

    assert tool.tags == tags_vals


def test_empty_tags_decorator():
    """Test that the default tags decorator attaches no tags to a tool."""

    @tags()
    def tool():
        pass

    assert tool.tags == []


def test_tags_returns_original_function():
    """The decorator must return the exact function it received, not a wrapper."""

    async def tool(x: int) -> int:
        return x

    decorated_tool = tags('tag')(tool)
    assert decorated_tool is tool
