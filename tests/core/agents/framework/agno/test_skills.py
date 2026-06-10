"""Tests for the skills module."""

import hashlib
import subprocess

import pytest

from agentorg.core.agents.framework.agno import GitHubSkills


def _cache_key(url: str, ref: str) -> str:
    return hashlib.sha1(f'{url}@{ref}'.encode(), usedforsecurity=False).hexdigest()[:12]


def test_defaults():
    """Unspecified options fall back to HEAD, no subpath, validation on."""
    loader = GitHubSkills('https://github.com/acme/skills')
    assert loader.url == 'https://github.com/acme/skills'
    assert loader.ref == 'HEAD'
    assert loader.subpath == ''
    assert loader.validate is True


def test_custom_attributes():
    """Explicit options are stored verbatim."""
    loader = GitHubSkills('https://github.com/acme/skills', ref='v1.2.0', subpath='packs/research', validate=False)
    assert loader.ref == 'v1.2.0'
    assert loader.subpath == 'packs/research'
    assert loader.validate is False


@pytest.mark.network
def test_clone_failure_propagates(cache_root):
    """A non-existent ref makes git fail, and the loader surfaces that rather than swallowing it."""
    loader = GitHubSkills('https://github.com/obra/superpowers', ref='no-such-ref-xyz')
    with pytest.raises(subprocess.CalledProcessError):
        loader.load()


@pytest.mark.network
def test_clone_is_cached_not_refetched(cache_root):
    """The first load clones; a second load with the same (url, ref) reuses the clone instead of refetching."""
    url, ref = 'https://github.com/upstash/context7', 'master'
    first = GitHubSkills(url, ref=ref, subpath='skills').load()
    assert {s.name for s in first}  # non-empty

    # A re-clone would wipe and recreate the dir, so a sentinel surviving proves the cache was reused.
    dest = cache_root / _cache_key(url, ref)
    sentinel = dest / '.agentorg-cache-probe'
    sentinel.write_text('x')

    second = GitHubSkills(url, ref=ref, subpath='skills').load()
    assert sentinel.exists()
    assert {s.name for s in second} == {s.name for s in first}
