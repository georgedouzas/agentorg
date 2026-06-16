"""Factories for `agno.Agent`, `agno.Team`, and `agno.Workflow` with agentorg defaults applied."""

from collections.abc import Callable, Iterable
from typing import Any, Literal, cast

from agno.agent import Agent
from agno.db.in_memory import InMemoryDb
from agno.guardrails.prompt_injection import PromptInjectionGuardrail
from agno.skills import Skills
from agno.skills.loaders.base import SkillLoader
from agno.team import Team, TeamMode
from agno.workflow import Step, Workflow

WHEN_TO_ACT_DEFAULT = [
    'Greetings or unclear messages: reply briefly and ask for a concrete request.',
    'Requests outside your scope (see below): decline and refer to the named agent.',
    'Concrete in-scope requests: run the workflow.',
]
STYLE_DEFAULT = [
    'Be concise. A direct answer beats an explanation of the answer.',
    'Do not restate your own role or these rules back to the user.',
    'Do not narrate tool calls, retries, or tool failures in your reply — the UI shows them as badges.',
]
SECTION_INTROS: dict[str, str] = {
    'principles': 'Org-wide rules every agent follows.',
    'when_to_act': 'When this agent engages versus stays quiet.',
    'style': 'Tone and format rules for every response.',
    'in_scope': 'Topics this agent owns.',
    'out_of_scope': 'Topics this agent declines, and the peer to refer to.',
    'workflow': 'Steps this agent follows for an in-scope request.',
}
AGENT_DEFAULTS: dict[str, Any] = {
    # Model fallbacks
    'fallback_config': None,
    'fallback_models': None,
    # Per-call identity
    'user_id': None,
    'session_id': None,
    # Session state
    'session_state': None,
    'add_session_state_to_context': False,
    'overwrite_db_session_state': False,
    'enable_agentic_state': False,
    'cache_session': True,
    # Past sessions
    'search_past_sessions': False,
    'num_past_sessions_to_search': None,
    'num_past_session_runs_in_search': None,
    'search_session_history': True,
    'num_history_sessions': 3,
    # Dependencies
    'dependencies': None,
    'add_dependencies_to_context': False,
    # Storage and memory
    'db': None,
    'memory_manager': None,
    'enable_agentic_memory': True,
    'update_memory_on_run': True,
    'enable_user_memories': True,
    'add_memories_to_context': True,
    'enable_session_summaries': True,
    'add_session_summary_to_context': True,
    'session_summary_manager': None,
    # Compression
    'compress_tool_results': False,
    'compression_manager': None,
    # Chat history
    'add_history_to_context': True,
    'num_history_runs': 10,
    'num_history_messages': None,
    'max_tool_calls_from_history': None,
    'store_media': True,
    'store_tool_messages': True,
    'store_history_messages': True,
    # Knowledge / RAG
    'knowledge': None,
    'knowledge_filters': None,
    'enable_agentic_knowledge_filters': None,
    'add_knowledge_to_context': False,
    'knowledge_retriever': None,
    'references_format': 'json',
    # Tools
    'metadata': None,
    'tool_call_limit': 20,
    'tool_choice': None,
    'tool_hooks': None,
    'pre_hooks': None,
    'post_hooks': None,
    # Reasoning
    'reasoning': True,
    'reasoning_model': None,
    'reasoning_agent': None,
    'reasoning_min_steps': 1,
    'reasoning_max_steps': 10,
    # History / knowledge read tools
    'read_chat_history': True,
    'search_knowledge': True,
    'add_search_knowledge_instructions': True,
    'update_knowledge': False,
    'read_tool_call_history': True,
    # Media
    'send_media_to_model': True,
    # System and user message
    'system_message': None,
    'system_message_role': 'system',
    'build_context': True,
    'instructions': None,
    'use_instruction_tags': True,
    'expected_output': None,
    'markdown': True,
    'add_name_to_context': False,
    'add_datetime_to_context': False,
    'add_location_to_context': False,
    'datetime_format': None,
    'timezone_identifier': None,
    'resolve_in_context': True,
    # Learning
    'learning': None,
    'add_learnings_to_context': True,
    'additional_input': None,
    # User message
    'user_message_role': 'user',
    'build_user_context': True,
    # Resilience
    'retries': 2,
    'delay_between_retries': 2,
    'exponential_backoff': True,
    # Parsing / structured i/o
    'parser_model': None,
    'parser_model_prompt': None,
    'input_schema': None,
    'output_schema': None,
    'parse_response': True,
    'output_model': None,
    'output_model_prompt': None,
    'structured_outputs': None,
    'use_json_mode': False,
    'save_response_to_file': None,
    # Followups
    'followups': False,
    'num_followups': 3,
    'followup_model': None,
    # Streaming
    'stream': None,
    'stream_events': None,
    'store_events': True,
    'events_to_skip': None,
    # Culture
    'culture_manager': None,
    'enable_agentic_culture': False,
    'update_cultural_knowledge': False,
    'add_culture_to_context': None,
    # Debug and telemetry
    'debug_mode': False,
    'debug_level': 1,
    'telemetry': True,
    # Callable caches
    'cache_callables': True,
    'callable_tools_cache_key': None,
    'callable_knowledge_cache_key': None,
}
TEAM_DEFAULTS: dict[str, Any] = {
    # Model fallbacks
    'fallback_config': None,
    'fallback_models': None,
    # Delegation
    'respond_directly': False,
    'determine_input_for_members': True,
    'delegate_to_all_members': False,
    'max_iterations': 10,
    # Per-call identity
    'user_id': None,
    'session_id': None,
    # Session state
    'session_state': None,
    'add_session_state_to_context': False,
    'enable_agentic_state': False,
    'overwrite_db_session_state': False,
    'resolve_in_context': True,
    'cache_session': True,
    # Team history
    'add_team_history_to_members': False,
    'num_team_history_runs': 3,
    # Past sessions
    'search_past_sessions': False,
    'num_past_sessions_to_search': None,
    'num_past_session_runs_in_search': None,
    'search_session_history': True,
    'num_history_sessions': 3,
    # System and user message
    'use_instruction_tags': True,
    'expected_output': None,
    'system_message': None,
    'system_message_role': 'system',
    'additional_input': None,
    # Context flags
    'add_datetime_to_context': False,
    'add_location_to_context': False,
    'datetime_format': None,
    'timezone_identifier': None,
    'add_name_to_context': False,
    'add_member_tools_to_context': False,
    # Dependencies
    'dependencies': None,
    'add_dependencies_to_context': False,
    # Knowledge / RAG
    'knowledge': None,
    'knowledge_filters': None,
    'add_knowledge_to_context': False,
    'enable_agentic_knowledge_filters': False,
    'update_knowledge': False,
    'knowledge_retriever': None,
    'references_format': 'json',
    # Member interaction
    'share_member_interactions': False,
    'get_member_information_tool': False,
    # History / knowledge read tools
    'search_knowledge': True,
    'add_search_knowledge_instructions': True,
    'read_chat_history': True,
    # Media
    'store_media': True,
    'store_tool_messages': True,
    'store_history_messages': True,
    'send_media_to_model': True,
    # Chat history
    'add_history_to_context': True,
    'num_history_runs': 10,
    'num_history_messages': None,
    'max_tool_calls_from_history': None,
    # Tools
    'skills': None,
    'tools': None,
    'tool_call_limit': 20,
    'tool_choice': None,
    'tool_hooks': None,
    'post_hooks': None,
    # Parsing / structured i/o
    'input_schema': None,
    'output_schema': None,
    'parser_model': None,
    'parser_model_prompt': None,
    'output_model': None,
    'output_model_prompt': None,
    'use_json_mode': False,
    'parse_response': True,
    # Storage and memory
    'enable_agentic_memory': True,
    'update_memory_on_run': True,
    'enable_user_memories': True,
    'add_memories_to_context': True,
    'memory_manager': None,
    'enable_session_summaries': True,
    'session_summary_manager': None,
    'add_session_summary_to_context': True,
    # Learning
    'learning': None,
    'add_learnings_to_context': True,
    # Compression
    'compress_tool_results': False,
    'compression_manager': None,
    # Metadata
    'metadata': None,
    # Reasoning
    'reasoning': True,
    'reasoning_model': None,
    'reasoning_agent': None,
    'reasoning_min_steps': 1,
    'reasoning_max_steps': 10,
    # Followups
    'followups': False,
    'num_followups': 3,
    'followup_model': None,
    # Streaming
    'stream': None,
    'stream_events': None,
    'store_events': True,
    'events_to_skip': None,
    'store_member_responses': True,
    'stream_member_events': True,
    # Debug and telemetry
    'debug_mode': False,
    'debug_level': 1,
    'show_members_responses': False,
    'telemetry': True,
    # Resilience
    'retries': 2,
    'delay_between_retries': 2,
    'exponential_backoff': True,
    # Output style
    'markdown': True,
    # Callable caches
    'cache_callables': True,
    'callable_tools_cache_key': None,
    'callable_knowledge_cache_key': None,
    'callable_members_cache_key': None,
}
WORKFLOW_DEFAULTS: dict[str, Any] = {
    # Step orchestration
    'agent': None,
    # Per-call identity
    'session_id': None,
    'user_id': None,
    # Session state
    'session_state': None,
    'overwrite_db_session_state': False,
    'add_session_state_to_context': None,
    'cache_session': True,
    # Streaming
    'stream': None,
    'stream_events': False,
    'stream_executor_events': True,
    'store_events': True,
    'events_to_skip': None,
    'store_executor_outputs': True,
    # Parsing / structured i/o
    'input_schema': None,
    # Metadata
    'metadata': None,
    # Dependencies
    'dependencies': None,
    'add_dependencies_to_context': None,
    # Workflow history
    'add_workflow_history_to_steps': False,
    'num_history_runs': 3,
    # Debug and telemetry
    'debug_mode': False,
    'debug_level': 1,
    'telemetry': True,
}
TOOLS_INTRO = 'The only tool names you are allowed to mention in chat. Everything else is silent.'
SKILLS_INTRO = 'The only skill names you are allowed to mention in chat. Everything else is silent.'
MEMBERS_INTRO = 'The only member names you are allowed to mention in chat. Everything else is silent.'


def _create_section(heading: str, intro: str, main: Iterable[str]) -> str:
    texts = [f'## {heading}', f'*{intro}*']
    bullet_points = '\n'.join([f"- {bullet_point}" for bullet_point in main])
    texts = [*texts, bullet_points]
    text = '\n\n'.join(texts)
    return text


def _compose_instructions(
    *,
    principles: Iterable[str],
    when_to_act: Iterable[str],
    in_scope: Iterable[str],
    out_of_scope: Iterable[str],
    workflow: Iterable[str],
    style: Iterable[str],
    extras: Iterable[tuple[str, str, Iterable[str]]] = (),
) -> str:
    """Compose an agent's (or team's) instructions from the standard six-section template.

    `extras` appends additional `(heading, intro, items)` sections in order; an entry whose `items` is empty is skipped.
    Agents pass Tools and Skills; teams pass Members.
    """
    sections: list[str] = []
    for name, main_text in [
        ('principles', principles),
        ('when_to_act', when_to_act),
        ('in_scope', in_scope),
        ('out_of_scope', out_of_scope),
        ('workflow', workflow),
        ('style', style),
    ]:
        heading = name.replace('_', ' ').capitalize()
        intro = SECTION_INTROS[name]
        section = _create_section(heading, intro, main_text)
        sections.append(section)

    for heading, intro, items in extras:
        items_list = list(items)
        if items_list:
            sections.append(_create_section(heading, intro, items_list))

    instructions = '\n\n'.join(sections)
    return instructions


def make_agent(
    *,
    model: str,
    name: str,
    agent_id: str,
    role: str,
    tools: list[Callable],
    in_scope: list[str],
    workflow: list[str],
    skills: list[SkillLoader] | None = None,
    introduction: str = '',
    description: str = '',
    additional_context: str = '',
    principles: list[str] | None = None,
    when_to_act: list[str] | None = None,
    out_of_scope: list[str] | None = None,
    style: list[str] | None = None,
    **kwargs: object,
) -> Agent:
    """Build a configured `agno.Agent` from agentorg's curated persona spec.

    Arguments:
        model: The language model the agent should use.
        name: Display name for the agent.
        agent_id: Unique identifier for the agent.
        role: Description of the agent's role.
        tools: A list of callables the agent can use as tools.
        in_scope: A list of topics the agent should consider in-scope.
        workflow: A list of steps the agent should follow when handling an in-scope request.
        skills: A list of `agno.skills.loaders.base.SkillLoader` instances. Empty by default.
        introduction: An introduction message the agent uses to greet users. Empty by default.
        description: Description of the agent. Empty by default.
        additional_context: Any extra context to inject into the system prompt. Empty by default.
        principles: Org-wide rules the agent should follow. Empty by default.
        when_to_act: Rules for when the agent engages versus stays quiet. Falls back to `WHEN_TO_ACT_DEFAULT`.
        out_of_scope: Topics the agent declines. Empty by default.
        style: Tone and format rules. Falls back to `STYLE_DEFAULT`.
        **kwargs: Extra `agno.Agent` configuration that overrides `AGENT_DEFAULTS`.

    Returns:
        agent: A configured `agno.Agent` instance.
    """
    skills = skills or []
    principles = principles or []
    out_of_scope = out_of_scope or []
    tool_names = [getattr(t, '__name__', None) or repr(t) for t in tools]
    skill_names = Skills(loaders=skills).get_skill_names() if skills else []
    instructions = _compose_instructions(
        principles=principles,
        when_to_act=when_to_act or WHEN_TO_ACT_DEFAULT,
        style=style or STYLE_DEFAULT,
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        workflow=workflow,
        extras=[
            ('Tools', TOOLS_INTRO, tool_names),
            ('Skills', SKILLS_INTRO, skill_names),
        ],
    )

    # Dynamic per-agent values
    dynamic: dict[str, Any] = {
        'db': InMemoryDb(),
        'instructions': instructions,
        'pre_hooks': [PromptInjectionGuardrail()],
        'skills': Skills(loaders=skills) if skills else None,
    }

    return Agent(
        id=agent_id,
        name=name,
        role=role,
        description=description,
        additional_context=additional_context,
        introduction=introduction,
        model=model,
        tools=tools,
        **{**AGENT_DEFAULTS, **dynamic, **kwargs},
    )


def make_team(
    *,
    model: str,
    members: list[Agent | Team],
    name: str,
    team_id: str,
    role: str,
    workflow: list[str],
    mode: Literal['coordinate', 'route', 'broadcast', 'tasks'] = 'coordinate',
    in_scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
    introduction: str = '',
    description: str = '',
    additional_context: str = '',
    principles: list[str] | None = None,
    when_to_act: list[str] | None = None,
    style: list[str] | None = None,
    **kwargs: object,
) -> Team:
    """Build an `agno.Team` with agentorg's defaults plus a composed persona prompt.

    The team's `instructions` are composed from the same six sections as `make_agent`
    (principles, when_to_act, in_scope, out_of_scope, workflow, style) plus a `Members`
    section listing the agents the team can delegate to.

    Arguments:
        model: The model the team uses to orchestrate delegation between members.
        members: The agents or sub-teams the team coordinates.
        name: Display name for the team.
        team_id: Unique identifier for the team.
        role: Short description of the team's responsibility.
        workflow: A list of steps describing how the team coordinates its members.
        mode: Coordination mode - one of `coordinate`, `route`, `broadcast`, `tasks`.
        in_scope: Topics the team handles. Empty by default.
        out_of_scope: Topics the team declines. Empty by default.
        introduction: Greeting the team uses when first engaged. Empty by default.
        description: Description of the team. Empty by default.
        additional_context: Extra context injected into the system prompt. Empty by default.
        principles: Org-wide rules the team should follow. Empty by default.
        when_to_act: Rules for when the team engages. Falls back to `WHEN_TO_ACT_DEFAULT`.
        style: Tone and format rules. Falls back to `STYLE_DEFAULT`.
        **kwargs: Extra `agno.Team` configuration that overrides `TEAM_DEFAULTS`.

    Returns:
        team: A configured `agno.Team` instance.
    """
    principles = principles or []
    in_scope = in_scope or []
    out_of_scope = out_of_scope or []
    member_names: list[str] = [str(getattr(m, 'name', None) or getattr(m, 'id', '?')) for m in members]
    instructions = _compose_instructions(
        principles=principles,
        when_to_act=when_to_act or WHEN_TO_ACT_DEFAULT,
        style=style or STYLE_DEFAULT,
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        workflow=workflow,
        extras=[('Members', MEMBERS_INTRO, member_names)],
    )
    dynamic: dict[str, Any] = {
        'db': InMemoryDb(),
        'instructions': instructions,
        'pre_hooks': [PromptInjectionGuardrail()],
    }
    return Team(
        id=team_id,
        name=name,
        model=model,
        members=members,
        mode=TeamMode(mode),
        role=role,
        description=description,
        additional_context=additional_context,
        introduction=introduction,
        **{**TEAM_DEFAULTS, **dynamic, **kwargs},
    )


def make_workflow(
    *,
    steps: list[Step],
    name: str,
    workflow_id: str,
    description: str = '',
    **kwargs: object,
) -> Workflow:
    """Build an `agno.Workflow` with agentorg's defaults applied.

    Unlike `make_agent` and `make_team`, workflows are pure orchestration of steps and have no
    `instructions` field. Persona (principles, style, etc.) is carried by the member agents the
    workflow's steps invoke.

    Arguments:
        steps: The ordered steps the workflow executes.
        name: Display name for the workflow.
        workflow_id: Unique identifier for the workflow.
        description: Optional description of what the workflow does.
        **kwargs: Extra `agno.Workflow` configuration that overrides `WORKFLOW_DEFAULTS`.

    Returns:
        workflow: A configured `agno.Workflow` instance.
    """
    dynamic: dict[str, Any] = {'db': InMemoryDb()}
    return Workflow(
        id=workflow_id,
        name=name,
        description=description,
        steps=cast(Any, steps),
        **{**WORKFLOW_DEFAULTS, **dynamic, **kwargs},
    )
