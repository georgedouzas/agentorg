"""Tests for the options module."""

from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import PermissionResultAllow

from agentorg.core.adapters.claude import build_agent_options, resolve_workspace
from agentorg.core.agents.tools import read_knowledge
from agentorg.core.spec import Spec


async def _allow(*_: object) -> PermissionResultAllow:
    return PermissionResultAllow()


def lookup_order(order_id: int) -> str:
    """Look up an order."""
    return str(order_id)


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """A skills directory holding one `triage` skill."""
    skill = tmp_path / 'skills' / 'triage'
    skill.mkdir(parents=True)
    (skill / 'SKILL.md').write_text('---\nname: triage\ndescription: Triage tickets.\n---\nSteps.\n')
    return tmp_path / 'skills'


def _spec(spec_dict_minimal: dict[str, Any], **agent: Any) -> Spec:
    spec_dict_minimal['ai']['agents'][0].update(agent)
    spec_dict_minimal['runtime']['env_vars']['required'] = [
        {'name': 'CRM_TOKEN', 'description': 'CRM token.', 'required_label': 'Prod'},
    ]
    return Spec.model_validate(spec_dict_minimal)


def _options(spec: Spec, tmp_path: Path, skills_dir: Path, **kwargs: Any) -> Any:
    return build_agent_options(
        spec.ai.agent('assistant'),
        spec,
        workspace=tmp_path / 'ws',
        skills_dir=skills_dir,
        org_tools=[read_knowledge],
        can_use_tool=_allow,
        **kwargs,
    )


def test_build_agent_options_maps_model_prompt_and_limits(
    spec_dict_minimal: dict[str, Any],
    tmp_path: Path,
    skills_dir: Path,
) -> None:
    """Model tier, system prompt, turn cap, budget and workspace map directly."""
    spec = _spec(spec_dict_minimal, model='haiku', limits={'max_turns': 7, 'max_run_usd': 0.5})
    options = _options(spec, tmp_path, skills_dir)
    assert options.model == 'haiku'
    assert options.system_prompt.startswith('You are Assistant')
    assert (options.max_turns, options.max_budget_usd) == (7, 0.5)
    assert options.cwd == tmp_path / 'ws'
    assert (tmp_path / 'ws').is_dir()


def test_build_agent_options_budget_defaults_to_org_per_run(
    spec_dict_minimal: dict[str, Any],
    tmp_path: Path,
    skills_dir: Path,
) -> None:
    """Without an agent cap, the org's per-run budget applies."""
    options = _options(_spec(spec_dict_minimal), tmp_path, skills_dir)
    assert options.max_budget_usd == 2.0


def test_build_agent_options_exposes_only_granted_builtins(
    spec_dict_minimal: dict[str, Any],
    tmp_path: Path,
    skills_dir: Path,
) -> None:
    """Built-ins come from the definition, nothing is auto-approved, and subagents are disallowed."""
    options = _options(_spec(spec_dict_minimal, autonomy='read_only'), tmp_path, skills_dir)
    assert options.tools == ['Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch', 'TodoWrite']
    assert options.allowed_tools == []
    assert options.disallowed_tools == ['Task', 'NotebookEdit']
    assert options.permission_mode == 'default'
    assert options.can_use_tool is _allow


def test_build_agent_options_serves_org_custom_and_external_servers(
    spec_dict_minimal: dict[str, Any],
    tmp_path: Path,
    skills_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Org and custom tools are in-process servers, and external servers read secrets from the environment."""
    monkeypatch.setenv('CRM_TOKEN', 's3cret')
    servers = [
        {'name': 'crm', 'transport': 'http', 'url': 'https://crm.example/mcp', 'env': ['CRM_TOKEN']},
        {'name': 'metrics', 'transport': 'stdio', 'command': 'metrics-mcp', 'args': ['--ro']},
    ]
    spec = _spec(spec_dict_minimal, tools=[lookup_order], mcp_servers=servers)
    mcp = _options(spec, tmp_path, skills_dir).mcp_servers
    assert set(mcp) == {'org', 'custom', 'crm', 'metrics'}
    assert (mcp['org']['type'], mcp['custom']['type']) == ('sdk', 'sdk')
    assert mcp['crm'] == {
        'type': 'http',
        'url': 'https://crm.example/mcp',
        'headers': {'Authorization': 'Bearer s3cret'},
    }
    assert mcp['metrics'] == {'type': 'stdio', 'command': 'metrics-mcp', 'args': ['--ro'], 'env': {}}


def test_build_agent_options_installs_only_declared_skills(
    spec_dict_minimal: dict[str, Any],
    tmp_path: Path,
    skills_dir: Path,
) -> None:
    """Declared skills are copied into the workspace and are the only skills enabled."""
    options = _options(_spec(spec_dict_minimal, skills=['triage']), tmp_path, skills_dir)
    assert options.skills == ['triage']
    assert options.setting_sources == ['project']
    assert (tmp_path / 'ws' / '.claude' / 'skills' / 'triage' / 'SKILL.md').exists()


def test_build_agent_options_isolates_agent_without_skills(
    spec_dict_minimal: dict[str, Any],
    tmp_path: Path,
    skills_dir: Path,
) -> None:
    """An agent without skills loads no filesystem settings and no skills, so host-level skills are absent."""
    options = _options(_spec(spec_dict_minimal), tmp_path, skills_dir)
    assert (options.setting_sources, options.skills) == ([], [])


def test_build_agent_options_requests_json_output(
    spec_dict_minimal: dict[str, Any],
    tmp_path: Path,
    skills_dir: Path,
) -> None:
    """A json output contract becomes a json_schema output format."""
    schema = {'type': 'object', 'properties': {'choice': {'type': 'string'}}}
    options = _options(_spec(spec_dict_minimal, output={'format': 'json', 'json_schema': schema}), tmp_path, skills_dir)
    assert options.output_format == {'type': 'json_schema', 'schema': schema}


@pytest.mark.parametrize(('memory', 'expected'), [('session', 'sdk-1'), ('none', None)])
def test_build_agent_options_resumes_only_with_memory(
    spec_dict_minimal: dict[str, Any],
    tmp_path: Path,
    skills_dir: Path,
    memory: str,
    expected: str | None,
) -> None:
    """A session is resumed unless the agent keeps no memory."""
    options = _options(_spec(spec_dict_minimal, memory=memory), tmp_path, skills_dir, resume='sdk-1')
    assert options.resume == expected


@pytest.mark.parametrize(
    ('workspace', 'expected'),
    [('ephemeral', 'runs/run-1'), ('persistent', 'agents/assistant'), ('shared', 'units/org')],
)
def test_resolve_workspace_by_mode(
    spec_dict_minimal: dict[str, Any],
    tmp_path: Path,
    workspace: str,
    expected: str,
) -> None:
    """Each workspace mode resolves to its own directory under the org root."""
    spec = _spec(spec_dict_minimal, workspace=workspace)
    assert resolve_workspace(spec.ai.agent('assistant'), spec, tmp_path, 'run-1') == tmp_path / expected
