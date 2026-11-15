"""Tests for the knowledge module."""

import re

import pytest

from agentorg.core.agents.tools import _knowledge


async def test_read_knowledge_returns_not_found_for_missing_unit(call):
    """Reading a unit that was never written returns the not-found message."""
    result = await call('read_knowledge', knowledge_type='report', name='nonexistent')
    assert result == "No report knowledge found for 'nonexistent'."


async def test_read_knowledge_returns_content_for_a_written_unit(call):
    """A unit with markdown content returns that content verbatim."""
    await call('write_knowledge', knowledge_type='report', name='q1', content='Q1 sales up 12%.')
    result = await call('read_knowledge', knowledge_type='report', name='q1')
    assert result == 'Q1 sales up 12%.'


async def test_write_knowledge_returns_confirmation(call):
    """`write_knowledge` confirms with a per-unit save message."""
    result = await call('write_knowledge', knowledge_type='confirm-test', name='basic', content='Body.')
    assert result == "Saved confirm-test 'basic' to knowledge."


async def test_write_knowledge_replaces_existing_unit(call):
    """Writing the same `(type, name)` twice replaces the content (no merge, no append)."""
    await call('write_knowledge', knowledge_type='mutable', name='evolving', content='Original.')
    await call('write_knowledge', knowledge_type='mutable', name='evolving', content='Updated.')
    result = await call('read_knowledge', knowledge_type='mutable', name='evolving')
    assert result == 'Updated.'


async def test_list_knowledge_filters_by_type(call):
    """`list_knowledge(knowledge_type=...)` lists only units of that type, in the canonical format."""
    await call('write_knowledge', knowledge_type='rpt', name='q1', content='Q1 sales up 12%.')
    await call('write_knowledge', knowledge_type='rpt', name='q2', content='Q2 sales up 15%.')
    await call('write_knowledge', knowledge_type='act', name='hedge-sell', content='Sell stocks.')
    result = await call('list_knowledge', knowledge_type='rpt')
    stripped = re.sub(r'\s*\(updated [^)]+\)', '', result)
    assert stripped == 'Rpt:\n  - q1\n  - q2'


async def test_list_knowledge_filters_by_metadata(call):
    """`list_knowledge(metadata_filter=...)` lists only units whose metadata is a superset of the filter."""
    await call('write_knowledge', knowledge_type='meta', name='q1', content='Q1.', metadata={'author': 'alice-uniq'})
    await call('write_knowledge', knowledge_type='meta', name='q2', content='Q2.', metadata={'author': 'alice-uniq'})
    await call('write_knowledge', knowledge_type='meta', name='q3', content='Q3.', metadata={'author': 'bob-uniq'})
    result = await call('list_knowledge', metadata_filter={'author': 'alice-uniq'})
    stripped = re.sub(r'\s*\(updated [^)]+\)', '', result)
    assert stripped == "Meta:\n  - q1 {'author': 'alice-uniq'}\n  - q2 {'author': 'alice-uniq'}"


async def test_list_knowledge_shows_title_when_set(call):
    """A unit written with a title appears as `{name} — {title}` in the listing."""
    await call('write_knowledge', knowledge_type='titled', name='greeting', content='Hello.', title='Greeting')
    result = await call('list_knowledge', knowledge_type='titled')
    stripped = re.sub(r'\s*\(updated [^)]+\)', '', result)
    assert stripped == 'Titled:\n  - greeting — Greeting'


async def test_list_knowledge_returns_empty_message_when_nothing_matches(call):
    """`list_knowledge` returns the empty message when no units satisfy the filter."""
    result = await call('list_knowledge', knowledge_type='no-such-type-xyzzy')
    assert result == 'No knowledge units found.'


async def test_search_knowledge_returns_no_match_message(call):
    """`search_knowledge` returns the no-match message when nothing satisfies the query."""
    result = await call('search_knowledge', query='xyzzy_definitely_no_match_8675309')
    assert result == "No knowledge units matching 'xyzzy_definitely_no_match_8675309'."


async def test_search_knowledge_finds_by_substring(call):
    """`search_knowledge` falls back to case-insensitive substring matching when no embedder is configured."""
    await call('write_knowledge', knowledge_type='search-substr', name='hit', content='unique_searchterm_alpha here.')
    await call('write_knowledge', knowledge_type='search-substr', name='miss', content='unrelated content.')
    result = await call('search_knowledge', query='unique_searchterm_alpha', knowledge_types=['search-substr'])
    assert 'search-substr/hit' in result
    assert 'search-substr/miss' not in result


async def test_search_knowledge_filters_by_types(call):
    """`search_knowledge(types=[...])` restricts the search to those types only."""
    await call('write_knowledge', knowledge_type='search-doc', name='in', content='matching_term_beta in scope.')
    await call('write_knowledge', knowledge_type='search-note', name='out', content='matching_term_beta out of scope.')
    result = await call('search_knowledge', query='matching_term_beta', knowledge_types=['search-doc'])
    assert 'search-doc/in' in result
    assert 'search-note/out' not in result


async def test_search_knowledge_caps_results_at_top_k(call):
    """`search_knowledge(top_k=N)` returns at most N hits."""
    written = 5
    top_k = 2
    for i in range(written):
        await call(
            'write_knowledge',
            knowledge_type='topk-target',
            name=f'unit-{i}',
            content=f'unique_topkmarker payload {i}.',
        )
    result = await call('search_knowledge', query='unique_topkmarker', knowledge_types=['topk-target'], top_k=top_k)
    assert result.count('**topk-target/') == top_k


async def test_delete_knowledge_returns_not_found_for_missing_unit(call):
    """`delete_knowledge` on a missing unit returns the not-found message."""
    result = await call('delete_knowledge', knowledge_type='disposable', name='never-existed-key')
    assert result == "No disposable knowledge found for 'never-existed-key'."


async def test_delete_knowledge_removes_existing_unit(call):
    """After delete, a follow-up read returns the not-found message."""
    await call('write_knowledge', knowledge_type='disposable', name='to-delete', content='Goodbye.')
    delete_result = await call('delete_knowledge', knowledge_type='disposable', name='to-delete')
    assert delete_result == "Deleted disposable 'to-delete'."
    read_result = await call('read_knowledge', knowledge_type='disposable', name='to-delete')
    assert read_result == "No disposable knowledge found for 'to-delete'."


async def test_write_knowledge_short_circuits_under_preview_mode(call, monkeypatch):
    """When `AGENTORG_PREVIEW_MODE=true`, write_knowledge returns a read-only message and does not persist."""
    monkeypatch.setenv('AGENTORG_PREVIEW_MODE', 'true')
    msg = await call(
        'write_knowledge',
        knowledge_type='disposable',
        name='preview-blocked',
        content='Should not land.',
    )
    assert 'preview mode' in msg.lower()
    assert 'disabled' in msg.lower()
    monkeypatch.setenv('AGENTORG_PREVIEW_MODE', 'false')
    read_msg = await call('read_knowledge', knowledge_type='disposable', name='preview-blocked')
    assert read_msg == "No disposable knowledge found for 'preview-blocked'."


async def test_delete_knowledge_short_circuits_under_preview_mode(call, monkeypatch):
    """When in preview mode, delete_knowledge also returns the read-only message."""
    monkeypatch.setenv('AGENTORG_PREVIEW_MODE', 'false')
    await call('write_knowledge', knowledge_type='disposable', name='preview-survives', content='Stays put.')

    monkeypatch.setenv('AGENTORG_PREVIEW_MODE', 'true')
    msg = await call('delete_knowledge', knowledge_type='disposable', name='preview-survives')
    assert 'preview mode' in msg.lower()

    monkeypatch.setenv('AGENTORG_PREVIEW_MODE', 'false')
    read_msg = await call('read_knowledge', knowledge_type='disposable', name='preview-survives')
    assert 'Stays put' in read_msg


async def test_search_knowledge_falls_back_when_the_embedder_fails(call, monkeypatch: pytest.MonkeyPatch):
    """A failing embedder, such as one without its API key, degrades writes and searches to substring matching."""

    async def no_key(**_kwargs: object) -> object:
        msg = 'Missing Gemini API key.'
        raise RuntimeError(msg)

    monkeypatch.setattr(_knowledge, '_embedder', lambda: 'google:gemini-embedding-001')
    monkeypatch.setattr('litellm.aembedding', no_key)
    await call('write_knowledge', knowledge_type='embed-down', name='hit', content='unique_embedfail_gamma here.')
    result = await call('search_knowledge', query='unique_embedfail_gamma', knowledge_types=['embed-down'])
    assert 'embed-down/hit' in result
