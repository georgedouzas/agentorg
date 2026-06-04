"""Factory for `agno.Agent` instances built from agentorg's persona spec."""

from collections.abc import Callable, Iterable
from typing import Any

from agno.agent import Agent
from agno.db.in_memory import InMemoryDb
from agno.guardrails.prompt_injection import PromptInjectionGuardrail
from agno.skills import Skills
from agno.skills.loaders.base import SkillLoader

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
AGNO_DEFAULTS: dict[str, Any] = {
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


def _create_section(heading: str, intro: str, main: Iterable[str]) -> list[str]:
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
    out_of_scope: Iterable[tuple[str, str]],
    workflow: Iterable[str],
    style: Iterable[str],
    tools_names: Iterable[str],
    skills_names: Iterable[str],
) -> str:
    """Compose an agent's instructions from the standard six-section template."""
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

    # Tools
    if tools_names:
        heading = 'Tools'
        intro = 'The only tools names you are allowed to mention in chat. Everything else is silent.'
        section = _create_section(heading, intro, tools_names)
        sections.append(section)

    # Skills
    if skills_names:
        heading = 'Skills'
        intro = 'The only skills names you are allowed to mention in chat. Everything else is silent.'
        section = _create_section(heading, intro, skills_names)
        sections.append(section)
    instructions = '\n\n'.join(sections)
    return instructions


def make_agent(
    *,
    model: str,
    name: str,
    agent_id: str,
    skills: list[SkillLoader],
    tools: list[Callable],
    introduction: str,
    description: str,
    additional_context: str,
    role: str,
    principles: list[str],
    when_to_act: list[str],
    in_scope: list[str],
    out_of_scope: list[tuple[str, str]],
    workflow: list[str],
    style: list[str],
    **kwargs: object,
) -> Agent:
    """Build a configured `agno.Agent` from agentorg's curated persona spec.

    Arguments:
        model: The language model the agent should use.
        name: Display name for the agent.
        agent_id: Unique identifier for the agent (passed to `agno.Agent` as `id`).
        skills: A list of `agno.skills.loaders.base.SkillLoader` instances for loading agent skills.
        tools: A list of callables the agent can use as tools.
        introduction: An introduction message the agent can use to greet users.
        description: Description of the agent.
        additional_context: Any additional context to include in the system prompt.
        role: Description of the agent's role.
        principles: A list of strings describing any org-wide principles the agent should follow.
        when_to_act: A list of rules describing when the agent should engage versus stay quiet.
        in_scope: A list of topics the agent should consider in-scope.
        out_of_scope: A list of tuples off (topic, referral) for topics the agent should consider out-of-scope.
        workflow: A list of steps the agent should follow when handling an in-scope request.
        style: A list of rules describing the tone and format of the agent's responses.
        **kwargs: Any additional configuration values for `agno.Agent` beyond the above, which are passed
            through directly and can override any of the defaults set in `AGNO_DEFAULTS`.

    Returns:
        agent: A configured `agno.Agent` instance.
    """
    tool_names = [getattr(t, '__name__', None) or repr(t) for t in tools]
    skill_names = Skills(loaders=skills).get_skill_names() if skills else []
    instructions = _compose_instructions(
        principles=principles,
        when_to_act=when_to_act or WHEN_TO_ACT_DEFAULT,
        style=style or STYLE_DEFAULT,
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        workflow=workflow,
        tools_names=tool_names,
        skills_names=skill_names,
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
        **{**AGNO_DEFAULTS, **dynamic, **kwargs},
    )
