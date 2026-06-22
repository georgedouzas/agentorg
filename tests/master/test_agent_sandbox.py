"""Tests for the agent_sandbox module."""

import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
from agno.agent import Agent
from agno.skills.loaders.base import SkillLoader
from agno.skills.loaders.local import LocalSkills

from agentorg.core.agents.skills import DEFAULT_SKILLS_REFS
from agentorg.core.agents.tools import read_knowledge
from agentorg.master import (
    AgentSpec,
    CustomSkill,
    CustomTool,
    add_or_update_agent,
    emit_custom_tool,
    sandbox_agent,
)
from agentorg.master._agent_sandbox import (
    AgentSandboxError,
    build_agent_from_spec,
    resolve_skill,
    resolve_tool,
)

VALID_TOOL_SOURCE = textwrap.dedent(
    '''
    """A simple custom tool that echoes its input."""

    async def echo_tool(message: str) -> str:
        """Return the message verbatim."""
        return f'echo: {message}'
    '''

       ,
).strip()


# ---- Tool resolver ----


def test_resolve_tool_returns_the_sandbox_stub_for_knowledge_tools():
    """Knowledge tools are swapped for sandbox stubs - the real ones need a reasoner context."""
    resolved = resolve_tool('read_knowledge', custom_tools=[])
    # NOT the real `read_knowledge` (which would fail in sandbox), but a stub coroutine.
    assert resolved is not read_knowledge
    assert callable(resolved)
    assert resolved.__name__.startswith('_stub_')


def test_resolve_tool_exec_s_a_custom_tools_source_and_returns_the_function():
    """A registered custom tool resolves to a callable derived from its source."""
    custom = CustomTool(name='echo_tool', source=VALID_TOOL_SOURCE)
    fn = resolve_tool('echo_tool', custom_tools=[custom])
    assert callable(fn)
    assert fn.__name__ == 'echo_tool'


def test_resolve_tool_raises_for_an_unknown_name():
    """A name that's neither built-in nor custom raises AgentSandboxError."""
    with pytest.raises(AgentSandboxError, match='unknown tool ref'):
        resolve_tool('nonexistent_tool', custom_tools=[])


# ---- Skill resolver ----


def test_resolve_skill_for_a_catalog_ref_returns_a_github_loader():
    """A bare catalog name produces a `GitHubSkills` loader."""
    loader = resolve_skill('superpowers', custom_skills=[], custom_skill_root=Path())
    assert isinstance(loader, SkillLoader)


def test_resolve_skill_for_a_granular_ref_extends_the_subpath():
    """A `'catalog/sub'` ref extends the catalog's subpath."""
    loader = resolve_skill('superpowers/foo', custom_skills=[], custom_skill_root=Path())
    expected_suffix = f'{DEFAULT_SKILLS_REFS["superpowers"]["subpath"]}/foo'
    assert loader.subpath.endswith(expected_suffix)


def test_resolve_skill_for_a_custom_ref_returns_a_local_loader_pointing_at_the_skill_dir(tmp_path: Path):
    """A `'custom:<name>'` ref points `LocalSkills` at `<root>/<name>`."""
    custom = CustomSkill(name='echo-skill', skill_md='# Echo\n\nReturns the input.')
    loader = resolve_skill('custom:echo-skill', custom_skills=[custom], custom_skill_root=tmp_path)
    assert isinstance(loader, LocalSkills)


def test_resolve_skill_rejects_unknown_custom_name(tmp_path: Path):
    """`'custom:never-registered'` fails fast rather than producing a broken loader."""
    with pytest.raises(AgentSandboxError, match='not registered'):
        resolve_skill('custom:never-registered', custom_skills=[], custom_skill_root=tmp_path)


def test_resolve_skill_rejects_unknown_catalog():
    """A nonexistent catalog name raises an explicit error."""
    with pytest.raises(AgentSandboxError, match='unknown skill catalog'):
        resolve_skill('totally-fake-catalog', custom_skills=[], custom_skill_root=Path())


# ---- build_agent_from_spec ----


def _tool_agent_spec() -> AgentSpec:
    return AgentSpec(
        agent_id='librarian',
        name='Librarian',
        role='Reads and writes knowledge units.',
        in_scope=['Cataloguing knowledge for the org.'],
        workflow=['Read the request.', 'Write the unit.'],
        tools=['read_knowledge', 'write_knowledge'],
    )


def test_build_agent_from_spec_returns_an_agno_agent_with_resolved_tools():
    """A spec with built-in tools instantiates into a real agno.Agent.

    Knowledge tools are resolved to sandbox stubs (`_stub_read_knowledge`, `_stub_write_knowledge`) so the run isn't
    blocked by the reasoner-context check.
    """
    agent = build_agent_from_spec(_tool_agent_spec(), custom_tools=[], custom_skills=[])
    assert isinstance(agent, Agent)
    assert agent.id == 'librarian'
    tool_names = {getattr(t, '__name__', None) for t in agent.tools}
    assert '_stub_read_knowledge' in tool_names
    assert '_stub_write_knowledge' in tool_names


def test_build_agent_from_spec_raises_when_custom_skill_root_is_missing():
    """A spec referencing a `custom:` skill without a root directory raises clearly."""
    spec = AgentSpec(
        agent_id='skilled',
        name='Skilled',
        role='Uses a custom skill.',
        in_scope=['x'],
        workflow=['y'],
        skills=['custom:my-skill'],
    )
    with pytest.raises(AgentSandboxError, match='custom_skill_root'):
        build_agent_from_spec(
            spec,
            custom_tools=[],
            custom_skills=[CustomSkill(name='my-skill', skill_md='# X\n\nbody.')],
        )


# ---- sandbox_agent patch tool ----


async def test_sandbox_agent_returns_a_friendly_message_for_unknown_agent_id():
    """Calling `sandbox_agent` with an `agent_id` not in the spec returns a hint, no crash."""
    result = await sandbox_agent(agent_id='ghost', test_prompts=['hi'])
    assert "No agent named 'ghost'" in result


async def test_sandbox_agent_returns_a_friendly_message_when_no_prompts_supplied():
    """Empty `test_prompts` is rejected with a helpful message."""
    add_or_update_agent(
        agent_id='librarian',
        name='Librarian',
        role='Reads and writes knowledge units.',
        in_scope=['Cataloguing.'],
        workflow=['Read.', 'Write.'],
        tools=['read_knowledge', 'write_knowledge'],
    )
    result = await sandbox_agent(agent_id='librarian', test_prompts=[])
    assert 'at least one test prompt' in result


async def test_sandbox_agent_executes_real_prompts_with_a_mocked_arun(monkeypatch: pytest.MonkeyPatch):
    """With `Agent.arun` mocked to return a canned RunOutput, the report contains the response + tool calls."""

    async def fake_arun(self, prompt: str, *args: object, **kwargs: object) -> object:
        return SimpleNamespace(content=f'replied to: {prompt}', tool_calls=[{'tool_name': 'read_knowledge'}])

    monkeypatch.setattr(Agent, 'arun', fake_arun)

    add_or_update_agent(
        agent_id='librarian',
        name='Librarian',
        role='Reads and writes knowledge units.',
        in_scope=['Cataloguing.'],
        workflow=['Read.', 'Write.'],
        tools=['read_knowledge', 'write_knowledge'],
    )
    result = await sandbox_agent(agent_id='librarian', test_prompts=['what units do we have?', 'log a unit'])
    assert '## Sandbox report for `librarian`' in result
    assert 'replied to: what units do we have?' in result
    assert 'replied to: log a unit' in result
    assert 'read_knowledge' in result


async def test_sandbox_agent_surfaces_a_build_failure_when_a_custom_tool_is_missing():
    """A spec that references an unregistered custom tool fails to build; the report says why."""
    add_or_update_agent(
        agent_id='broken',
        name='Broken Agent',
        role='Has a reference to a tool that does not exist.',
        in_scope=['Nothing real.'],
        workflow=['Try to use ghost_tool.'],
        tools=['ghost_tool'],
    )
    result = await sandbox_agent(agent_id='broken', test_prompts=['hello'])
    assert 'could not be built' in result
    assert 'ghost_tool' in result


async def test_sandbox_agent_runs_against_a_custom_tool_with_a_real_body(monkeypatch: pytest.MonkeyPatch):
    """A custom tool registered via emit_custom_tool is resolved and the sandbox surfaces the agent's response."""
    emit_custom_tool(
        name='echo_tool',
        source=VALID_TOOL_SOURCE,
        test_cases=[{'input': {'message': 'hi'}, 'expected_contains': 'echo: hi'}],
    )
    add_or_update_agent(
        agent_id='echoer',
        name='Echoer',
        role='Echoes user input.',
        in_scope=['Echoing things back.'],
        workflow=['Receive a message.', 'Echo it via echo_tool.'],
        tools=['echo_tool'],
    )

    async def fake_arun(self, prompt: str, *args: object, **kwargs: object) -> object:
        return SimpleNamespace(content='ok', tool_calls=[{'tool_name': 'echo_tool'}])

    monkeypatch.setattr(Agent, 'arun', fake_arun)
    result = await sandbox_agent(agent_id='echoer', test_prompts=['say hello'])
    assert 'echo_tool' in result
