"""Tests for base module."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from agentorg.core import render
from agentorg.core.quality import find_layout_violations


@pytest.fixture
def write_spec_py(spec_dict_minimal: dict[str, Any]) -> Callable[..., Path]:
    """Factory: writes a minimal `spec.py` into a directory and returns its path."""

    def write(spec_dir: Path, **org_overrides: object) -> Path:
        spec_dict = {**spec_dict_minimal, 'org': {**spec_dict_minimal['org'], **org_overrides}}
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_py = spec_dir / 'spec.py'
        spec_py.write_text(f'from agentorg.core.spec import Spec\nspec = Spec.model_validate({spec_dict!r})\n')
        return spec_py

    return write


@pytest.mark.parametrize(
    ('template', 'must_contain'),
    [
        ('full', ['pyproject.toml', 'src/acme/spec.py', 'src/frontend/package.json']),
        ('frontend', ['package.json', 'vite.config.ts', 'src/App.tsx']),
        ('backend', ['pyproject.toml', 'src/acme/spec.py', 'src/acme/app/main.py', 'tests/app/test_routes.py']),
        ('ai', ['pyproject.toml', 'src/acme/spec.py', 'src/acme/sandbox.py', 'src/acme/ai/__init__.py']),
    ],
)
def test_each_shipped_template_renders(
    write_spec_py: Callable[..., Path],
    tmp_path: Path,
    template: str,
    must_contain: list[str],
) -> None:
    """Each shipped template renders against a minimal spec and produces its signature files."""
    spec_py = write_spec_py(tmp_path / 'spec')
    output = tmp_path / 'out'
    render(spec_py, output, template=template)
    for relpath in must_contain:
        assert (output / relpath).exists(), f'{template}: expected {relpath} to exist'


@pytest.mark.parametrize('template', ['full', 'backend', 'ai'])
def test_each_python_template_renders_mirrored_tests(
    write_spec_py: Callable[..., Path],
    tmp_path: Path,
    template: str,
) -> None:
    """Each Python template renders a project whose tests mirror its source tree."""
    output = tmp_path / 'out'
    render(write_spec_py(tmp_path / 'spec'), output, template=template)
    assert find_layout_violations(output) == []


def test_spec_py_is_copied_into_rendered_package(write_spec_py: Callable[..., Path], tmp_path: Path) -> None:
    """The user's `spec.py` ends up at `<output>/src/<package>/spec.py` for runtime import."""
    spec_py = write_spec_py(tmp_path / 'spec')
    output = tmp_path / 'out'
    render(spec_py, output, template='full')
    copied = output / 'src' / 'acme' / 'spec.py'
    assert copied.exists()
    assert copied.read_text() == spec_py.read_text()


def test_railway_render_lists_rabbitmq_setup_step(spec_dict_minimal: dict[str, Any], tmp_path: Path) -> None:
    """A Railway org's rendered README carries the step that provisions RabbitMQ and sets AMQP_URL."""
    spec_dict_minimal['runtime']['infra'] |= {'packaging': 'docker', 'api': 'railway'}
    spec_py = tmp_path / 'spec' / 'spec.py'
    spec_py.parent.mkdir()
    spec_py.write_text(f'from agentorg.core.spec import Spec\nspec = Spec.model_validate({spec_dict_minimal!r})\n')
    render(spec_py, tmp_path / 'out', template='full')
    readme = (tmp_path / 'out' / 'README.md').read_text()
    assert 'Provision RabbitMQ' in readme
    assert '`AMQP_URL`' in readme


def test_skills_next_to_spec_are_copied_into_package(write_spec_py: Callable[..., Path], tmp_path: Path) -> None:
    """A `skills/` folder next to spec.py lands in the rendered package, where agents load skills from."""
    spec_py = write_spec_py(tmp_path / 'spec')
    skill = tmp_path / 'spec' / 'skills' / 'triage' / 'SKILL.md'
    skill.parent.mkdir(parents=True)
    skill.write_text('---\nname: triage\ndescription: Triage.\n---\nSteps.\n')
    render(spec_py, tmp_path / 'out', template='full')
    assert (tmp_path / 'out' / 'src' / 'acme' / 'skills' / 'triage' / 'SKILL.md').read_text().startswith('---')


INTERFACE_KEYS_V087 = {
    'customWelcome',
    'modelSelect',
    'parameters',
    'presets',
    'prompts',
    'agents',
    'mcpServers',
    'memories',
    'fileSearch',
    'fileCitations',
    'runCode',
    'webSearch',
    'marketplace',
    'privacyPolicy',
    'termsOfService',
    'multiConvo',
    'bookmarks',
    'temporaryChat',
    'peoplePicker',
    'defaultPinnedTools',
    'buildInfo',
}


def _render_normal(spec_dict: dict[str, Any], tmp_path: Path) -> Path:
    spec_py = tmp_path / 'spec' / 'spec.py'
    spec_py.parent.mkdir()
    spec_py.write_text(f'from agentorg.core.spec import Spec\nspec = Spec.model_validate({spec_dict!r})\n')
    render(spec_py, tmp_path / 'out', template='full')
    return tmp_path / 'out'


def test_librechat_render_configures_model_specs(spec_dict_normal: dict[str, Any], tmp_path: Path) -> None:
    """A LibreChat org gets one enforced model spec per agent and unit, served by the node's chat API."""
    out = _render_normal(spec_dict_normal, tmp_path)
    config = yaml.safe_load((out / 'librechat.yaml').read_text())
    agents = [agent['id'] for agent in spec_dict_normal['ai']['agents']]
    endpoint = config['endpoints']['custom'][0]
    specs = {item['name']: item for item in config['modelSpecs']['list']}
    assert config['version'] == '1.3.13'
    assert set(config['interface']) <= INTERFACE_KEYS_V087
    assert endpoint['headers']['X-Agentorg-User-Id'] == '{{LIBRECHAT_USER_ID}}'
    assert endpoint['headers']['X-Agentorg-User-Email'] == '{{LIBRECHAT_USER_EMAIL}}'
    assert endpoint['headers']['X-Agentorg-Conversation-Id'] == '{{LIBRECHAT_BODY_CONVERSATIONID}}'
    assert set(endpoint['models']['default']) == set(specs) >= set(agents)
    assert config['modelSpecs']['enforce'] is True
    assert [name for name, item in specs.items() if item['default']] == ['analyst']
    assert specs['researcher']['label'] == '📚 Researcher'
    assert {item['preset']['endpoint'] for item in specs.values()} == {endpoint['name']}


def test_librechat_render_disables_bypasses(spec_dict_normal: dict[str, Any], tmp_path: Path) -> None:
    """LibreChat's own agents, MCP, tools and model switching are off, and only the custom endpoint is enabled."""
    out = _render_normal(spec_dict_normal, tmp_path)
    interface = yaml.safe_load((out / 'librechat.yaml').read_text())['interface']
    compose = yaml.safe_load((out / 'compose.yaml').read_text())
    off = [
        'modelSelect',
        'parameters',
        'presets',
        'prompts',
        'agents',
        'fileSearch',
        'runCode',
        'webSearch',
        'memories',
    ]
    assert not any(interface[key] for key in off)
    assert interface['mcpServers'] == {'use': False, 'create': False}
    assert 'ENDPOINTS=custom' in compose['services']['librechat']['environment']


def test_librechat_render_adds_services_and_env(spec_dict_normal: dict[str, Any], tmp_path: Path) -> None:
    """The compose stack pins LibreChat and wires the shared chat key into the node and LibreChat."""
    out = _render_normal(spec_dict_normal, tmp_path)
    services = yaml.safe_load((out / 'compose.yaml').read_text())['services']
    api = next(service for name, service in services.items() if name.endswith('-api'))
    assert services['librechat']['image'] == 'ghcr.io/danny-avila/librechat:v0.8.7'
    assert {'librechat-mongodb', 'librechat-meilisearch'} <= set(services)
    assert 'CHAT_API_KEY=${CHAT_API_KEY}' in api['environment']
    assert 'CHAT_API_KEY=${CHAT_API_KEY}' in services['librechat']['environment']
    env = (out / 'example.env').read_text()
    assert env.count('CHAT_API_KEY=') == 1
    assert 'LIBRECHAT_CREDS_KEY=' in env


def test_local_render_configures_librechat_without_compose(spec_dict_minimal: dict[str, Any], tmp_path: Path) -> None:
    """Without docker the org still gets its LibreChat configuration and README instructions to run it."""
    out = _render_normal(spec_dict_minimal, tmp_path)
    assert yaml.safe_load((out / 'librechat.yaml').read_text())['modelSpecs']['enforce'] is True
    assert not (out / 'compose.yaml').exists()
    assert 'Run LibreChat yourself' in (out / 'README.md').read_text()
