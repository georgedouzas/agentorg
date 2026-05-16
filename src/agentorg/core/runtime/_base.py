"""Adapt spec runnables into AgentField reasoners."""

import re
from typing import Any

# Strip reasoning traces (Gemini-style `<thinking>...</thinking>` blocks) before showing the answer
# to the user; the model still benefits from chain-of-thought, the chat UI stays clean.
_THINKING_PATTERN = re.compile(r'<thinking>.*?</thinking>', re.DOTALL | re.IGNORECASE)


def _clean_output(text: str) -> str:
    return _THINKING_PATTERN.sub('', text).strip()

# Defaults applied to every agno-style agent that doesn't already configure these capabilities itself.
# Designed so a freshly-registered agent supports rolling chat history per session, per-user memories
# that accumulate across sessions, a chain-of-thought reasoning pass, agentic memory/culture so the
# agent can curate its own learnings, resilience on transient model failures, and richer event
# capture for the control plane.
AGNO_DEFAULTS: dict[str, Any] = {
    # Rolling chat history
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


def _build_learning_machine(db: Any) -> Any:
    """Build an agno `LearningMachine` with all default learning stores enabled."""
    from agno.learn.machine import LearningMachine  # noqa: PLC0415 — defer heavy import
    return LearningMachine(
        db=db,
        user_profile=True,    # accumulate what the agent learns about each user
        user_memory=True,     # explicit user memories
        session_context=True, # rolling context across sessions
        entity_memory=True,   # remember named entities the agent reasons about
        learned_knowledge=True,  # general learnings extracted from runs
        decision_log=True,    # log of decisions for later reflection
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
    # Attach a learning machine wired to the same db so cross-session learnings, decision logs,
    # and entity memory persist alongside chat history.
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
        result = await arun(message, session_id=session_id, user_id=user_id)
        raw = getattr(result, 'content', None) or str(result)
        return {'output': _clean_output(raw)}

    _run.__name__ = name
    reasoner(name=name, tags=tags)(_run)
    return name
