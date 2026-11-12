"""Tests for the intake module."""

import pytest

from agentorg.core.operations import admit_all, payload_tags


@pytest.mark.parametrize(
    ('payload', 'tags'),
    [
        ({'tags': ['billing', 7]}, ['billing', '7']),
        ({'tags': 'billing'}, []),
        ({'body': 1}, []),
        (['tags'], []),
        (None, []),
    ],
)
def test_payload_tags_reads_only_a_tags_list(payload: object, tags: list[str]) -> None:
    """Only a `tags` list in a dict payload yields routing tags, as strings."""
    assert payload_tags(payload) == tags


async def test_admit_all_accepts_every_target() -> None:
    """The default admission accepts work for any target."""
    assert await admit_all('anything') is None
