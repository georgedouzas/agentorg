"""Shared fixtures for the `agentorg.core.render` and `agentorg.core.spec` modules."""

from typing import Any

import pytest
from agno.agent import Agent
from agno.team import Team
from agno.workflow import Step, Workflow


@pytest.fixture
def org_dict_minimal() -> dict[str, Any]:
    """Minimal Org dict with every required key at its lightest value."""
    return {
        'name': 'Acme',
        'slug': 'acme',
        'package_name': 'acme',
        'description': '',
        'repository': '',
        'admin_name': '',
        'admin_email': '',
        'visibility': 'private',
        'budget': 'medium',
    }


@pytest.fixture
def org_dict_normal() -> dict[str, Any]:
    """Normal Org dict with realistic populated values."""
    return {
        'name': 'Acme Organization',
        'slug': 'acme-org',
        'package_name': 'acme_org',
        'description': 'Makes widgets.',
        'repository': 'https://github.com/acme/acme_org',
        'admin_name': 'A. Coyote',
        'admin_email': 'coyote@acme.com',
        'visibility': 'private',
        'budget': 'medium',
    }


@pytest.fixture
def runtime_dict_minimal() -> dict[str, Any]:
    """Minimal Runtime dict on the local stack with no env vars or setup steps."""
    return {
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


@pytest.fixture
def runtime_dict_normal() -> dict[str, Any]:
    """Normal Runtime dict on a docker + postgres + pgvector stack with one env var and one setup step."""
    return {
        'infra': {
            'packaging': 'docker',
            'database': 'postgres',
            'vector_db': 'pgvector',
            'embedder': 'openai:text-embedding-3-small',
            'api': 'none',
            'frontend': 'none',
            'auth': 'none',
        },
        'env_vars': {
            'required': [{'name': 'GOOGLE_API_KEY', 'description': 'Gemini API key.', 'required_label': 'Prod'}],
            'optional': [],
        },
        'setup': [
            {
                'id': 'secrets',
                'title': 'Set keys',
                'description': 'Add the key to `.env`.',
                'variables': ['GOOGLE_API_KEY'],
            },
        ],
    }


@pytest.fixture
def ai_dict_minimal() -> dict[str, Any]:
    """Minimal AI dict with empty agents, teams, and workflows."""
    return {'agents': [], 'teams': [], 'workflows': [], 'framework': 'agno'}


@pytest.fixture
def ai_dict_normal() -> dict[str, Any]:
    """Normal AI dict carrying one agent, one team that wraps it, and a one-step workflow."""
    researcher = Agent(id='researcher', name='Researcher', instructions='Gather sources.')
    team = Team(id='research-team', name='Research Team', members=[researcher])
    workflow = Workflow(id='pipeline', name='Pipeline', steps=[Step(name='Gather', agent=researcher)])
    return {'agents': [researcher], 'teams': [team], 'workflows': [workflow], 'framework': 'agno'}


@pytest.fixture
def parameters_list_minimal() -> list[dict[str, Any]]:
    """Minimal parameters list."""
    return []


@pytest.fixture
def parameters_list_normal() -> list[dict[str, Any]]:
    """Normal parameters list with one int parameter."""
    return [{'name': 'min_sources', 'type': 'int', 'default': 3, 'label': 'Min Sources', 'format': None}]


@pytest.fixture
def knowledge_dict_minimal() -> dict[str, Any]:
    """Minimal Knowledge dict with no principles and no types."""
    return {'principles': {'sections': []}, 'types': []}


@pytest.fixture
def knowledge_dict_normal() -> dict[str, Any]:
    """Normal Knowledge dict carrying one principle section and one knowledge type."""
    return {
        'principles': {'sections': [{'id': 'mission', 'title': 'Mission', 'body': '- Do good work.'}]},
        'types': [
            {
                'id': 'report',
                'label': 'Reports',
                'metadata_fields': [{'name': 'author', 'type': 'string'}],
            },
        ],
    }


@pytest.fixture
def ui_dict_minimal() -> dict[str, Any]:
    """Minimal UI dict with all required keys at their lightest values."""
    return {
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


@pytest.fixture
def ui_dict_normal() -> dict[str, Any]:
    """Normal UI dict populated with a group, featured agent, icons, overview block, agent config, and quick prompt."""
    return {
        'app': {'name': 'Org', 'icon': '🔬', 'description': 'A research org.'},
        'empty_state': {'icon': '🔬', 'title': 'Pick an agent', 'body': 'Try the pipeline.'},
        'knowledge_empty': 'No knowledge yet.',
        'agent_groups': [{'label': 'Research Team', 'ids': ['researcher', 'analyst']}],
        'workflow_groups': [],
        'featured_agents': ['analyst'],
        'agent_icons': {'researcher': '📚'},
        'overview': [{'title': 'Mission', 'body': 'We **publish** structured analysis.'}],
        'agent_configs': {
            'researcher': {
                'model': 'google:gemini-2.5-flash',
                'description': 'Gathers sources.',
                'tools': ['search'],
                'features': [],
            },
        },
        'chat_quick_prompts': {'researcher': ['Summarise the topic']},
    }


@pytest.fixture
def spec_dict_minimal(
    org_dict_minimal: dict[str, Any],
    runtime_dict_minimal: dict[str, Any],
    ai_dict_minimal: dict[str, Any],
    parameters_list_minimal: list[dict[str, Any]],
    knowledge_dict_minimal: dict[str, Any],
    ui_dict_minimal: dict[str, Any],
) -> dict[str, Any]:
    """Minimal Spec dict assembled from the per-sub-model minimal fixtures."""
    return {
        'org': org_dict_minimal,
        'runtime': runtime_dict_minimal,
        'ai': ai_dict_minimal,
        'parameters': parameters_list_minimal,
        'knowledge': knowledge_dict_minimal,
        'ui': ui_dict_minimal,
    }


@pytest.fixture
def spec_dict_normal(
    org_dict_normal: dict[str, Any],
    runtime_dict_normal: dict[str, Any],
    ai_dict_normal: dict[str, Any],
    parameters_list_normal: list[dict[str, Any]],
    knowledge_dict_normal: dict[str, Any],
    ui_dict_normal: dict[str, Any],
) -> dict[str, Any]:
    """Normal Spec dict assembled from the per-sub-model normal fixtures."""
    return {
        'org': org_dict_normal,
        'runtime': runtime_dict_normal,
        'ai': ai_dict_normal,
        'parameters': parameters_list_normal,
        'knowledge': knowledge_dict_normal,
        'ui': ui_dict_normal,
    }
