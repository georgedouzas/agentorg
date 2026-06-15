"""Tests for the server module."""

from typing import Any

import pytest

from agentorg.core.adapters.mcp._server import _discover_skills, _tool_for

SKILLS_LIST = [
    {'id': 'write_knowledge', 'description': 'Save a unit.'},
    {'id': 'read_knowledge', 'description': 'Read a unit.'},
]


class _FakeResponse:
    """Minimal stand-in for `httpx.Response` exposing only the surface `_discover_skills` uses."""

    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class _FakeClient:
    """Captures the URL `_discover_skills` calls and returns a canned payload."""

    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.last_url: str | None = None

    async def get(self, url: str) -> _FakeResponse:
        self.last_url = url
        return _FakeResponse(self._payload)


def test_tool_for_uses_id_as_the_mcp_name():
    """The MCP `Tool.name` is the skill's `id`."""
    tool = _tool_for({'id': 'write_knowledge', 'description': 'Save a unit.'})
    assert tool.name == 'write_knowledge'


def test_tool_for_falls_back_to_name_when_id_missing():
    """When the skill has no `id`, the MCP `Tool.name` falls back to `name`."""
    tool = _tool_for({'name': 'fallback_skill', 'description': 'Has only name.'})
    assert tool.name == 'fallback_skill'


def test_tool_for_falls_back_to_unknown_when_neither_set():
    """A skill with neither `id` nor `name` gets the literal name `unknown`."""
    tool = _tool_for({'description': 'No identifier.'})
    assert tool.name == 'unknown'


def test_tool_for_uses_description_verbatim_and_appends_tags():
    """`description` is preserved; tags appear as `(tags: a, b)` after the description."""
    tool = _tool_for({'id': 'write_knowledge', 'description': 'Save a unit.', 'tags': ['knowledge', 'curation']})
    assert tool.description == 'Save a unit. (tags: knowledge, curation)'


def test_tool_for_omits_tag_suffix_when_no_tags():
    """No tags → no `(tags: ...)` suffix; description appears alone."""
    tool = _tool_for({'id': 'write_knowledge', 'description': 'Save a unit.'})
    assert tool.description == 'Save a unit.'


def test_tool_for_synthesises_description_when_skill_has_none():
    """A skill with no description gets `agentorg skill `<id>`` as a placeholder."""
    tool = _tool_for({'id': 'mystery_skill'})
    assert tool.description == 'agentorg skill `mystery_skill`'


def test_tool_for_passes_input_schema_through_unchanged():
    """The skill's `input_schema` becomes the MCP `Tool.inputSchema` verbatim."""
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    tool = _tool_for({'id': 'write_knowledge', 'input_schema': schema})
    assert tool.inputSchema == schema


def test_tool_for_uses_permissive_schema_fallback_when_missing():
    """No `input_schema` → permissive object schema (any properties accepted)."""
    tool = _tool_for({'id': 'write_knowledge'})
    assert tool.inputSchema == {'type': 'object', 'properties': {}, 'additionalProperties': True}


@pytest.mark.asyncio
async def test_discover_skills_returns_list_when_payload_is_already_a_list():
    """A bare-list `/skills` response passes through."""
    client = _FakeClient(SKILLS_LIST)
    result = await _discover_skills(client, 'http://node:8000')
    assert result == SKILLS_LIST


@pytest.mark.asyncio
async def test_discover_skills_unwraps_skills_key_from_envelope():
    """When the response is wrapped in `{'skills': [...]}`, the inner list is returned."""
    client = _FakeClient({'skills': SKILLS_LIST, 'extra': 'ignored'})
    result = await _discover_skills(client, 'http://node:8000')
    assert result == SKILLS_LIST


@pytest.mark.asyncio
async def test_discover_skills_returns_empty_list_for_unrecognised_payload():
    """A dict without `skills` key (and without being a list) yields the empty list — defensive default."""
    client = _FakeClient({'unexpected': 'shape'})
    result = await _discover_skills(client, 'http://node:8000')
    assert result == []


@pytest.mark.asyncio
async def test_discover_skills_strips_trailing_slash_from_node_url():
    """Trailing slash on the node URL doesn't produce a double-slash in the GET path."""
    client = _FakeClient([])
    await _discover_skills(client, 'http://node:8000/')
    assert client.last_url == 'http://node:8000/skills'


@pytest.mark.asyncio
async def test_discover_skills_appends_skills_path_to_node_url():
    """The function hits `<node_url>/skills`, not the root."""
    client = _FakeClient([])
    await _discover_skills(client, 'http://node:8000')
    assert client.last_url == 'http://node:8000/skills'
