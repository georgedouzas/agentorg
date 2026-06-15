"""Tests for the refs module."""

from agentorg.core.agents.skills import DEFAULT_SKILLS_REFS

_EXPECTED_FIELDS = {'url', 'ref', 'subpath', 'validate'}
_FIELD_TYPES = {'url': str, 'ref': str, 'subpath': str, 'validate': bool}


def test_default_skills_refs_has_expected_catalogues():
    """`DEFAULT_SKILLS_REFS` ships the well-known agent skill repos."""
    assert set(DEFAULT_SKILLS_REFS) == {'superpowers', 'context7', 'awesome-copilot'}


def test_each_entry_carries_the_full_field_set():
    """Every entry has exactly `url`, `ref`, `subpath`, and `validate` — no missing or extra keys."""
    for name, entry in DEFAULT_SKILLS_REFS.items():
        assert set(entry) == _EXPECTED_FIELDS, f'{name}: fields differ'


def test_each_field_has_the_declared_type():
    """`url`, `ref`, `subpath` are strings; `validate` is a bool."""
    for name, entry in DEFAULT_SKILLS_REFS.items():
        for field, expected_type in _FIELD_TYPES.items():
            assert isinstance(entry[field], expected_type), f'{name}.{field}: expected {expected_type.__name__}'


def test_urls_point_to_github():
    """The registry only ships GitHub-hosted catalogues today."""
    for name, entry in DEFAULT_SKILLS_REFS.items():
        assert entry['url'].startswith('https://github.com/'), f'{name}: non-GitHub url'
