"""Adapt spec runnables into AgentField reasoners."""

import re
from contextvars import ContextVar
from typing import Any

# Identity of the agent (or workflow / team) currently driving a reasoner run. Tools called inside
# `arun` read this to stamp `metadata.agent_id` and `metadata.agent_name` on whatever they produce
# (e.g. write_knowledge auto-tags every doc with the agent that authored it).
CALLING_AGENT: ContextVar[dict[str, str] | None] = ContextVar('agentorg_calling_agent', default=None)


def set_calling_agent(runnable: object) -> None:
    """Stash the running runnable's identity for the current async context."""
    aid = runnable_name(runnable)
    name = getattr(runnable, 'name', None) or aid
    CALLING_AGENT.set({'id': aid, 'name': name})


def get_calling_agent() -> dict[str, str] | None:
    """Return `{id, name}` of the agent driving the current run, or None if called outside one."""
    return CALLING_AGENT.get()

# Strip reasoning traces (Gemini-style `<thinking>...</thinking>` blocks) before showing the answer
# to the user; the model still benefits from chain-of-thought, the chat UI stays clean.
_THINKING_PATTERN = re.compile(r'<thinking>.*?</thinking>', re.DOTALL | re.IGNORECASE)


def _clean_output(text: str) -> str:
    return _THINKING_PATTERN.sub('', text).strip()

# Defaults applied to every agno-style agent that doesn't already configure these capabilities itself.
# The agentic flags below DO add framework tools (`update_user_memory`,
# `create_or_update_cultural_knowledge`, `save_learning`, `log_decision`, …) to the agent's
# palette. We keep them ON so the agent can self-curate memory + learning + culture in the
# background, and we hide their invocations from the chat UI via `FRAMEWORK_TOOL_NAMES` so only
# spec-declared business tools surface as badges.
AGNO_DEFAULTS: dict[str, Any] = {
    # Rolling chat history (passive injection + on-demand tools)
    'add_history_to_context': True,
    'num_history_runs': 10,
    'read_chat_history': True,
    'read_tool_call_history': True,
    # User-level memory that accumulates across sessions
    'enable_user_memories': True,
    'add_memories_to_context': True,
    'update_memory_on_run': True,
    # Agentic memory + culture: the agent owns and updates its own learnings + shared org culture
    'enable_agentic_memory': True,
    'enable_agentic_culture': True,
    'update_cultural_knowledge': True,
    'add_culture_to_context': True,
    # Periodic session summaries to keep long sessions affordable
    'enable_session_summaries': True,
    'add_session_summary_to_context': True,
    # Search across prior sessions when the agent decides it's relevant
    'search_session_history': True,
    'num_history_sessions': 3,
    # Chain-of-thought reasoning before each answer
    'reasoning': True,
    # Resilience against transient model failures
    'retries': 2,
    'exponential_backoff': True,
    'delay_between_retries': 2,
    # Cap runaway tool loops so a bad reasoning chain can't burn budget
    'tool_call_limit': 20,
    # Cache the session in-process so repeated turns avoid re-hydrating from db each time
    'cache_session': True,
    # Capture run events for the control plane's execution-DAG audit
    'store_events': True,
}


# Tools agno adds to the agent's palette for its internal bookkeeping (memory, culture, learning,
# history). They MUST be available to the LLM so it can curate state silently — but they're hidden
# from the chat UI (no tool badges) and the agent is instructed not to list them in chat replies,
# so the user only sees spec-declared "business" tools.
FRAMEWORK_TOOL_NAMES: frozenset[str] = frozenset({
    # Memory & culture
    'update_user_memory',
    'search_user_memories',
    'create_or_update_cultural_knowledge',
    'search_cultural_knowledge',
    # Chat / tool-call history
    'get_chat_history',
    'search_chat_history',
    'get_tool_call_history',
    'search_session_history',
    # Learning machine: learned_knowledge + decision_log stores
    'save_learning',
    'search_learnings',
    'log_decision',
    'search_decisions',
    'record_outcome',
})


def _build_learning_machine(db: Any) -> Any:
    """Build an agno `LearningMachine` with all default learning stores enabled."""
    from agno.learn.machine import LearningMachine  # noqa: PLC0415 — defer heavy import
    return LearningMachine(
        db=db,
        user_profile=True,
        user_memory=True,
        session_context=True,
        entity_memory=True,
        learned_knowledge=True,
        decision_log=True,
    )


def _build_prompt_guard() -> Any | None:
    """Return a prompt-injection guardrail instance, or None if agno's guard isn't importable."""
    try:
        from agno.guardrails.prompt_injection import PromptInjectionGuardrail  # noqa: PLC0415
    except ImportError:
        return None
    return PromptInjectionGuardrail()


def runnable_name(runnable: object) -> str:
    """Best-effort stable name for a runnable: `.id`, then `.name`, then `.__name__`."""
    name = getattr(runnable, 'id', None) or getattr(runnable, 'name', None) or getattr(runnable, '__name__', None)
    return str(name) if name else 'unnamed'


def _ensure_agno_defaults(runnable: object) -> None:
    """Enable the standard agno capability set on a runnable that hasn't configured it explicitly.

    No-op for non-agno runnables (plain async callables) and for runnables that already declare a `db`
    (we treat a user-supplied db as a signal that the spec author owns the configuration).
    Storage is in-process only; swap in `agno.db.sqlite.SqliteDb` for cross-restart persistence.
    """
    if not hasattr(runnable, 'db'):
        return
    if getattr(runnable, 'db', None) is not None:
        return
    try:
        from agno.db.in_memory import InMemoryDb  # noqa: PLC0415 — agno import is heavy, defer until needed
    except ImportError:
        return
    runnable.db = InMemoryDb()
    for attr, value in AGNO_DEFAULTS.items():
        if hasattr(runnable, attr) and getattr(runnable, attr) in (None, False, 0):
            setattr(runnable, attr, value)
    # Learning machine: wire decision-log + learned-knowledge + entity memory to the same db so
    # cross-session learning works in the background. The LLM-callable tools it adds are filtered
    # from the chat UI via FRAMEWORK_TOOL_NAMES.
    if hasattr(runnable, 'learning') and getattr(runnable, 'learning', None) is None:
        try:
            runnable.learning = _build_learning_machine(runnable.db)
        except Exception:  # noqa: BLE001 — agno learning is opt-in; never fail the boot for it
            pass
    # Prepend a prompt-injection guardrail unless the spec author already configured pre-hooks.
    if hasattr(runnable, 'pre_hooks') and not getattr(runnable, 'pre_hooks', None):
        guard = _build_prompt_guard()
        if guard is not None:
            runnable.pre_hooks = [guard]


def register_runnable(app: object, runnable: object, tags: list[str] | None = None) -> str:
    """Register `runnable` as a reasoner on the AgentField `app`; return the reasoner name.

    A plain async callable is registered as-is. An object exposing `.arun()` is wrapped in a
    `message -> {"output": ...}` reasoner that forwards `session_id`/`user_id` so agno's memory
    can scope history per chat. `tags` are attached so control-plane policies can target it.
    """
    name = runnable_name(runnable)
    reasoner = getattr(app, 'reasoner')  # noqa: B009 — duck-typed AgentField node
    tags = tags or []

    if callable(runnable) and not hasattr(runnable, 'arun'):
        reasoner(name=name, tags=tags)(runnable)
        return name

    _ensure_agno_defaults(runnable)
    arun = getattr(runnable, 'arun')  # noqa: B009 — agno-style runnable

    async def _run(message: str, session_id: str | None = None, user_id: str = 'default') -> dict[str, Any]:
        set_calling_agent(runnable)
        result = await arun(message, session_id=session_id, user_id=user_id)
        raw = getattr(result, 'content', None) or str(result)
        return {'output': _clean_output(raw)}

    _run.__name__ = name
    reasoner(name=name, tags=tags)(_run)
    return name
