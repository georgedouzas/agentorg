"""Behavioural sandbox: build an `agno.Agent` from an `AgentSpec` and run real prompts against it.

This is the engine behind the `sandbox_agent` patch tool used in Stage 4 of the interview.
Tool callables are resolved from the built-in catalog or by `exec()`-ing the source of a
custom tool registered via `emit_custom_tool` (the source has already been validated in a
subprocess at emit time). Skill loaders are resolved from `DEFAULT_SKILLS_REFS` or, for
`'custom:<name>'` refs, by materialising the registered SKILL.md into a temporary directory.

Running the constructed agent calls the real model and executes its real tools - including
any external-side-effect calls those tools make. Callers are expected to be explicit about
that risk with the user.
"""

import tempfile
from pathlib import Path
from typing import Any

from agno.skills.loaders.base import SkillLoader
from agno.skills.loaders.local import LocalSkills

from agentorg.core.agents import tools as builtin_tools
from agentorg.core.agents.framework.agno import GitHubSkills, make_agent
from agentorg.core.agents.skills import DEFAULT_SKILLS_REFS

from ._models import AgentSpec, CustomSkill, CustomTool

BUILTIN_TOOL_NAMES = (
    'read_knowledge',
    'write_knowledge',
    'list_knowledge',
    'search_knowledge',
    'delete_knowledge',
)


# Sandbox stubs for the knowledge tools. The real tools require an active reasoner
# execution context to reach `app.memory`, which the sandbox doesn't have (the agent
# runs from a plain `agno.Agent.arun` call, not from inside a node). The stubs return
# canned responses so the LLM sees "the tool worked" and the run completes - good enough
# for validating that the agent CALLS the right tools and HANDLES their output, which is
# what the sandbox is for.

async def _stub_read_knowledge(knowledge_type: str, name: str) -> str:
    """Sandbox stub for `read_knowledge`."""
    return f'[sandbox stub] would read knowledge unit ({knowledge_type!r}, {name!r}).'


async def _stub_write_knowledge(
    knowledge_type: str,
    name: str,
    title: str,
    content: str,
    metadata: dict | None = None,
) -> str:
    """Sandbox stub for `write_knowledge`."""
    _ = (content, metadata)  # accept the args without using them; LLM still sees a success
    return f'[sandbox stub] would write knowledge unit ({knowledge_type!r}, {name!r}, title={title!r}).'


async def _stub_list_knowledge(knowledge_type: str, metadata_filter: dict | None = None) -> str:
    """Sandbox stub for `list_knowledge`."""
    _ = metadata_filter
    return f'[sandbox stub] would list knowledge units of type {knowledge_type!r} (none in sandbox).'


async def _stub_search_knowledge(knowledge_type: str, query: str, k: int = 5) -> str:
    """Sandbox stub for `search_knowledge`."""
    return f'[sandbox stub] would search {knowledge_type!r} for {query!r} (top-{k}).'


async def _stub_delete_knowledge(knowledge_type: str, name: str) -> str:
    """Sandbox stub for `delete_knowledge`."""
    return f'[sandbox stub] would delete knowledge unit ({knowledge_type!r}, {name!r}).'


_SANDBOX_KNOWLEDGE_STUBS: dict[str, Any] = {
    'read_knowledge':   _stub_read_knowledge,
    'write_knowledge':  _stub_write_knowledge,
    'list_knowledge':   _stub_list_knowledge,
    'search_knowledge': _stub_search_knowledge,
    'delete_knowledge': _stub_delete_knowledge,
}


class AgentSandboxError(Exception):
    """Raised when an agent cannot be built (tool/skill resolution failed)."""


def resolve_tool(name: str, custom_tools: list[CustomTool]) -> Any:  # noqa: ANN401 (returns a callable; agno is permissive)
    """Resolve a tool ref string to its real callable.

    Built-in catalog names come from `agentorg.core.agents.tools`. The knowledge tools
    specifically are swapped for sandbox stubs (the real ones need an active reasoner
    execution context to reach `app.memory`). Custom tools are exec'd in a fresh
    namespace and the named function is returned. Custom source is expected to have
    already passed `validate_tool_source` at emit time.

    Arguments:
        name: Tool ref string from `AgentSpec.tools`.
        custom_tools: The current state's `custom_tools` list.

    Returns:
        callable: The resolved tool function (real or sandbox-stub).

    Raises:
        AgentSandboxError: If the name is neither a known built-in nor a registered custom tool.
    """
    # Tools use BARE names; the LLM sometimes prefixes `custom:` (it confuses the skill
    # format for the tool format). Strip the prefix so both forms resolve.
    name = name.removeprefix('custom:')
    if name in _SANDBOX_KNOWLEDGE_STUBS:
        return _SANDBOX_KNOWLEDGE_STUBS[name]
    if name in BUILTIN_TOOL_NAMES:
        return getattr(builtin_tools, name)
    for custom in custom_tools:
        if custom.name == name:
            namespace: dict[str, Any] = {}
            try:
                exec(custom.source, namespace)  # noqa: S102 (validated source by design)
            except Exception as exc:
                msg = f"custom tool {name!r} failed to import: {exc}"
                raise AgentSandboxError(msg) from exc
            fn = namespace.get(name)
            if not callable(fn):
                msg = f"custom tool {name!r} did not produce a callable"
                raise AgentSandboxError(msg)
            return fn
    msg = f'unknown tool ref {name!r} (not a built-in catalog name and not a registered custom tool)'
    raise AgentSandboxError(msg)


def resolve_skill(ref: str, custom_skills: list[CustomSkill], custom_skill_root: Path) -> SkillLoader:
    """Resolve a skill ref string to a `SkillLoader` instance.

    Forms supported (see writer for symmetry):
        - `'catalog'`           -> `GitHubSkills(**DEFAULT_SKILLS_REFS['catalog'])`.
        - `'catalog/subpath'`   -> `GitHubSkills(...)` with the catalog subpath extended.
        - `'custom:<name>'`     -> `LocalSkills(custom_skill_root / name)`. Caller materialises
                                   the SKILL.md before this is called.

    Arguments:
        ref: Skill ref string.
        custom_skills: Currently registered custom skills, for name resolution.
        custom_skill_root: Directory under which custom skills have been materialised.

    Returns:
        loader: The resolved `SkillLoader`.

    Raises:
        AgentSandboxError: If the ref is malformed or references something unknown.
    """
    if ref.startswith('custom:'):
        name = ref.removeprefix('custom:')
        if not any(c.name == name for c in custom_skills):
            msg = f"custom skill {name!r} is not registered (call emit_custom_skill first)"
            raise AgentSandboxError(msg)
        return LocalSkills(str(custom_skill_root / name))
    catalog, _, sub = ref.partition('/')
    if catalog not in DEFAULT_SKILLS_REFS:
        msg = f'unknown skill catalog {catalog!r}; expected one of {sorted(DEFAULT_SKILLS_REFS)}'
        raise AgentSandboxError(msg)
    cfg = DEFAULT_SKILLS_REFS[catalog]
    subpath = str(cfg['subpath'])
    return GitHubSkills(
        url=str(cfg['url']),
        ref=str(cfg['ref']),
        subpath=f'{subpath}/{sub}' if sub else subpath,
        validate=bool(cfg['validate']),
    )


def _materialise_custom_skills(custom_skills: list[CustomSkill], root: Path) -> None:
    """Write each registered custom skill's SKILL.md into `root/<name>/SKILL.md`."""
    for skill in custom_skills:
        target = root / skill.name
        target.mkdir(parents=True, exist_ok=True)
        (target / 'SKILL.md').write_text(skill.skill_md)


def build_agent_from_spec(
    agent_spec: AgentSpec,
    custom_tools: list[CustomTool],
    custom_skills: list[CustomSkill],
    *,
    custom_skill_root: Path | None = None,
) -> Any:  # noqa: ANN401 (returns an agno.Agent; avoid leaking that type in our API)
    """Construct a real `agno.Agent` from an `AgentSpec`.

    Tools and skills are resolved through `resolve_tool` / `resolve_skill`. Any custom skills
    must have been materialised on disk under `custom_skill_root` (or use the default temp
    directory the caller manages).

    Arguments:
        agent_spec: The agent spec to instantiate.
        custom_tools: Currently registered custom tools.
        custom_skills: Currently registered custom skills.
        custom_skill_root: Directory under which custom skills live. Required if `agent_spec`
            references any `'custom:'` skills.

    Returns:
        agent: A configured `agno.Agent`.

    Raises:
        AgentSandboxError: If tool/skill resolution fails.
    """
    if agent_spec.skills and any(s.startswith('custom:') for s in agent_spec.skills) and custom_skill_root is None:
        msg = 'custom skill refs require `custom_skill_root` to be set'
        raise AgentSandboxError(msg)
    tools = [resolve_tool(name, custom_tools) for name in agent_spec.tools]
    skills = [resolve_skill(ref, custom_skills, custom_skill_root or Path()) for ref in agent_spec.skills]
    kwargs: dict[str, Any] = {
        'model': agent_spec.model,
        'name': agent_spec.name,
        'agent_id': agent_spec.agent_id,
        'role': agent_spec.role,
        'in_scope': agent_spec.in_scope,
        'workflow': agent_spec.workflow,
        'tools': tools,
        'skills': skills,
    }
    if agent_spec.when_to_act:
        kwargs['when_to_act'] = agent_spec.when_to_act
    if agent_spec.out_of_scope:
        kwargs['out_of_scope'] = agent_spec.out_of_scope
    if agent_spec.style:
        kwargs['style'] = agent_spec.style
    if agent_spec.principles:
        kwargs['principles'] = agent_spec.principles
    if agent_spec.introduction:
        kwargs['introduction'] = agent_spec.introduction
    if agent_spec.description:
        kwargs['description'] = agent_spec.description
    if agent_spec.additional_context:
        kwargs['additional_context'] = agent_spec.additional_context
    return make_agent(**kwargs)


def _extract_tool_calls(run_output: Any) -> list[str]:  # noqa: ANN401 (agno's RunOutput shape is loose)
    """Pull a flat list of tool-call names out of an agno `RunOutput`."""
    tool_calls = getattr(run_output, 'tool_calls', None) or []
    names: list[str] = []
    for call in tool_calls:
        name = (
            getattr(call, 'tool_name', None)
            or getattr(call, 'name', None)
            or (call.get('tool_name') if isinstance(call, dict) else None)
            or (call.get('name') if isinstance(call, dict) else None)
        )
        if name:
            names.append(str(name))
    return names


async def sandbox_run(
    agent_spec: AgentSpec,
    test_prompts: list[str],
    custom_tools: list[CustomTool],
    custom_skills: list[CustomSkill],
) -> str:
    """Build the agent and run each test prompt against it; return a human-readable report.

    Real model and real tools execute. The caller is responsible for warning the user about
    side-effect risk before invoking this.

    Arguments:
        agent_spec: The agent to exercise.
        test_prompts: One or more prompts to run sequentially.
        custom_tools: Currently registered custom tools.
        custom_skills: Currently registered custom skills.

    Returns:
        report: A markdown report covering each prompt's response, tool calls, and any errors.
    """
    lines: list[str] = [f'## Sandbox report for `{agent_spec.agent_id}`']
    with tempfile.TemporaryDirectory(prefix='agentorg-sandbox-') as tmp:
        skill_root = Path(tmp)
        _materialise_custom_skills(custom_skills, skill_root)
        try:
            agent = build_agent_from_spec(
                agent_spec,
                custom_tools=custom_tools,
                custom_skills=custom_skills,
                custom_skill_root=skill_root,
            )
        except AgentSandboxError as exc:
            lines.append(f'**Agent could not be built:** {exc}')
            return '\n'.join(lines)

        for index, prompt in enumerate(test_prompts, start=1):
            lines.append(f'\n### Prompt {index}: {prompt}')
            try:
                run_output = await agent.arun(prompt)
            except Exception as exc:  # noqa: BLE001 - surface any runtime failure to the user
                lines.append(f'**Error:** {type(exc).__name__}: {exc}')
                continue
            tool_calls = _extract_tool_calls(run_output)
            lines.append(f'**Tool calls:** {", ".join(tool_calls) if tool_calls else "(none)"}')
            content = getattr(run_output, 'content', None) or ''
            lines.append(f'**Response:**\n{content.strip()}')
    return '\n'.join(lines)
