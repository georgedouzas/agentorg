"""Tests for the base module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import Spec

_MINIMAL_RUNTIME: dict[str, Any] = {
    'infra': {
        'packaging': 'none',
        'database': 'sqlite',
        'vector_db': 'chromadb',
        'embedder': 'google:text-embedding-004',
        'api': 'none',
        'frontend': 'none',
        'auth': 'none',
    },
    'env_vars': {'required': [], 'optional': []},
    'setup': [],
}
_MINIMAL_KNOWLEDGE: dict[str, Any] = {'principles': {'sections': []}, 'types': []}
_MINIMAL_UI: dict[str, Any] = {
    'app': {'name': 'Acme', 'icon': '🤖', 'description': ''},
    'empty_state': {'icon': '🤖', 'title': 'Pick an agent', 'body': ''},
    'knowledge_empty': '',
    'agent_groups': [],
    'workflow_groups': [],
    'featured_agents': [],
    'agent_icons': {},
    'overview': [],
    'agent_configs': {},
    'chat_quick_prompts': {},
}
_MINIMAL_ORG: dict[str, Any] = {
    'name': 'Acme',
    'slug': 'acme',
    'package_name': 'acme',
    'description': '',
    'repository': '',
    'admin_name': '',
    'admin_email': '',
    'visibility': 'private',
}
_MINIMAL: dict[str, Any] = {
    'org': _MINIMAL_ORG,
    'runtime': _MINIMAL_RUNTIME,
    'ai': {'agents': [], 'teams': [], 'workflows': []},
    'parameters': [],
    'knowledge': _MINIMAL_KNOWLEDGE,
    'ui': _MINIMAL_UI,
}


def test_spec_round_trips_minimal_config() -> None:
    """A minimal `Spec` constructed from dicts validates and exposes every sub-model."""
    spec = Spec.model_validate(_MINIMAL)
    assert spec.org.slug == 'acme'
    assert spec.runtime.infra.packaging == 'none'
    assert spec.ai.framework == 'agno'
    assert spec.parameters == []
    assert spec.knowledge.principles.sections == []
    assert spec.ui.app.name == 'Acme'


@pytest.mark.parametrize('missing', ['org', 'runtime', 'ai', 'parameters', 'knowledge', 'ui'])
def test_top_level_fields_are_all_required(missing: str) -> None:
    """Omitting any of `org`, `runtime`, `ai`, `parameters`, `knowledge`, `ui` fails validation."""
    fields = {k: v for k, v in _MINIMAL.items() if k != missing}
    with pytest.raises(ValidationError):
        Spec.model_validate(fields)
