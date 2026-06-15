"""Tests for the knowledge module."""

import re


async def test_read_knowledge_returns_not_found_for_missing_unit(call):
    """Reading a unit that was never written returns the not-found message."""
    result = await call('read_knowledge', type='report', name='nonexistent')
    assert result == "No report knowledge found for 'nonexistent'."


async def test_read_knowledge_returns_content_for_a_written_unit(call):
    """A unit with markdown content returns that content verbatim."""
    await call('write_knowledge', type='report', name='q1', content='Q1 sales up 12%.')
    result = await call('read_knowledge', type='report', name='q1')
    assert result == 'Q1 sales up 12%.'


async def test_write_knowledge_returns_confirmation(call):
    """`write_knowledge` confirms with a per-unit save message."""
    result = await call('write_knowledge', type='confirm-test', name='basic', content='Body.')
    assert result == "Saved confirm-test 'basic' to knowledge."


async def test_write_knowledge_replaces_existing_unit(call):
    """Writing the same `(type, name)` twice replaces the content (no merge, no append)."""
    await call('write_knowledge', type='mutable', name='evolving', content='Original.')
    await call('write_knowledge', type='mutable', name='evolving', content='Updated.')
    result = await call('read_knowledge', type='mutable', name='evolving')
    assert result == 'Updated.'


async def test_list_knowledge_filters_by_type(call):
    """`list_knowledge(knowledge_type=...)` lists only units of that type, in the canonical format."""
    await call('write_knowledge', type='rpt', name='q1', content='Q1 sales up 12%.')
    await call('write_knowledge', type='rpt', name='q2', content='Q2 sales up 15%.')
    await call('write_knowledge', type='act', name='hedge-sell', content='Sell stocks.')
    result = await call('list_knowledge', knowledge_type='rpt')
    stripped = re.sub(r'\s*\(updated [^)]+\)', '', result)
    assert stripped == 'Rpt:\n  - q1\n  - q2'


async def test_list_knowledge_filters_by_metadata(call):
    """`list_knowledge(metadata_filter=...)` lists only units whose metadata is a superset of the filter."""
    await call('write_knowledge', type='meta', name='q1', content='Q1.', metadata={'author': 'alice-uniq'})
    await call('write_knowledge', type='meta', name='q2', content='Q2.', metadata={'author': 'alice-uniq'})
    await call('write_knowledge', type='meta', name='q3', content='Q3.', metadata={'author': 'bob-uniq'})
    result = await call('list_knowledge', metadata_filter={'author': 'alice-uniq'})
    stripped = re.sub(r'\s*\(updated [^)]+\)', '', result)
    assert stripped == "Meta:\n  - q1 {'author': 'alice-uniq'}\n  - q2 {'author': 'alice-uniq'}"


async def test_list_knowledge_shows_title_when_set(call):
    """A unit written with a title appears as `{name} — {title}` in the listing."""
    await call('write_knowledge', type='titled', name='greeting', content='Hello.', title='Greeting')
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
    await call('write_knowledge', type='search-substr', name='hit', content='unique_searchterm_alpha here.')
    await call('write_knowledge', type='search-substr', name='miss', content='unrelated content.')
    result = await call('search_knowledge', query='unique_searchterm_alpha', types=['search-substr'])
    assert 'search-substr/hit' in result
    assert 'search-substr/miss' not in result


async def test_search_knowledge_filters_by_types(call):
    """`search_knowledge(types=[...])` restricts the search to those types only."""
    await call('write_knowledge', type='search-doc', name='in-scope', content='matching_term_beta in scope.')
    await call('write_knowledge', type='search-note', name='out-of-scope', content='matching_term_beta out of scope.')
    result = await call('search_knowledge', query='matching_term_beta', types=['search-doc'])
    assert 'search-doc/in-scope' in result
    assert 'search-note/out-of-scope' not in result


async def test_search_knowledge_caps_results_at_top_k(call):
    """`search_knowledge(top_k=N)` returns at most N hits."""
    written = 5
    top_k = 2
    for i in range(written):
        await call('write_knowledge', type='topk-target', name=f'unit-{i}', content=f'unique_topkmarker payload {i}.')
    result = await call('search_knowledge', query='unique_topkmarker', types=['topk-target'], top_k=top_k)
    assert result.count('**topk-target/') == top_k


async def test_delete_knowledge_returns_not_found_for_missing_unit(call):
    """`delete_knowledge` on a missing unit returns the not-found message."""
    result = await call('delete_knowledge', type='disposable', name='never-existed-key')
    assert result == "No disposable knowledge found for 'never-existed-key'."


async def test_delete_knowledge_removes_existing_unit(call):
    """After delete, a follow-up read returns the not-found message."""
    await call('write_knowledge', type='disposable', name='to-delete', content='Goodbye.')
    delete_result = await call('delete_knowledge', type='disposable', name='to-delete')
    assert delete_result == "Deleted disposable 'to-delete'."
    read_result = await call('read_knowledge', type='disposable', name='to-delete')
    assert read_result == "No disposable knowledge found for 'to-delete'."
