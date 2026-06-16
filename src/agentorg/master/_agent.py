"""The master agent."""

import os
from collections.abc import Callable
from textwrap import dedent
from typing import Any

from agno.agent import Agent
from agno.db.in_memory import InMemoryDb
from agno.run.agent import RunOutput
from dotenv import load_dotenv

from ._tools import (
    add_or_update_agent,
    add_or_update_agent_group,
    add_or_update_env_var,
    add_or_update_knowledge_type,
    add_or_update_overview_block,
    add_or_update_parameter,
    add_or_update_principle_section,
    add_or_update_setup_step,
    add_or_update_team,
    add_or_update_workflow,
    emit_custom_tool,
    finalize_spec,
    get_current_spec,
    list_placeholders,
    remove_agent,
    remove_agent_group,
    remove_custom_tool,
    remove_env_var,
    remove_knowledge_type,
    remove_overview_block,
    remove_parameter,
    remove_principle_section,
    remove_setup_step,
    remove_team,
    remove_workflow,
    set_agent_icons,
    set_featured_agents,
    set_knowledge_empty,
    set_org_identity,
    set_runtime_infra,
    set_ui_app,
    set_ui_empty_state,
)

load_dotenv()

MASTER_TOOLS: list[Callable[..., object]] = [
    list_placeholders,
    get_current_spec,
    set_org_identity,
    add_or_update_agent,
    remove_agent,
    add_or_update_team,
    remove_team,
    add_or_update_workflow,
    remove_workflow,
    add_or_update_parameter,
    remove_parameter,
    add_or_update_knowledge_type,
    remove_knowledge_type,
    add_or_update_principle_section,
    remove_principle_section,
    set_runtime_infra,
    add_or_update_env_var,
    remove_env_var,
    add_or_update_setup_step,
    remove_setup_step,
    set_ui_app,
    set_ui_empty_state,
    set_knowledge_empty,
    add_or_update_agent_group,
    remove_agent_group,
    set_featured_agents,
    set_agent_icons,
    add_or_update_overview_block,
    remove_overview_block,
    emit_custom_tool,
    remove_custom_tool,
    finalize_spec,
]

MASTER_INTRODUCTION = dedent(
    """
    Hi! I'm the agentorg master agent. I'll interview you, one focused question at a time, to
    assemble a complete `spec.py` for your multi-agent organisation.

    - Describe what the org should do and I'll fill in sensible defaults, or just say "go" and
      I'll walk you through the essentials.
    - Any answer is editable later. Say "change X to Y" any time.
    - When you're happy, I'll write the spec to disk.

    Let's start: what kind of organisation do you want to build?
    """,
).strip()

MASTER_INSTRUCTIONS = dedent(
    """
    You are the agentorg master agent.

    Your job is to interview the user and assemble a complete `spec.py` that describes their
    multi-agent organisation. The working spec is always valid - every required field is seeded
    with a placeholder that you replace as you learn the answer.

    Two pieces of live context are injected into your prompt every turn:
    - `working_spec`: a JSON snapshot of the current spec.
    - `placeholders`: the list of fields still holding seed values.

    HARD RULE: Always end with text the user can read
    - Every assistant turn MUST end with at least one human-readable sentence. Empty responses
      are forbidden.
    - When you call tools, the model can keep generating after the tool result. ALWAYS continue
      after tool calls with a short summary of what changed and the next question.
    - If you cannot decide what to do, ask the user a clarifying question. Anything is better
      than going silent.
    - Concrete check before you stop: "did I produce visible text this turn?". If no, write a
      one-line summary or question before ending.

    Principles
    - Treat `placeholders` as the interview to-do list. The interview ends when it is empty and
      the user confirms they are happy.
    - Always keep the working spec valid - patches go through Pydantic validation.
    - Tools must be plug-and-play. Use built-in catalog tool names when possible; emit
      `emit_custom_tool` only when no catalog tool fits, and only for small async functions you
      can write confidently.
    - Every field is editable at any time. If the user revisits a previous answer, apply the
      patch immediately and confirm.

    Validate before you patch
    - Sanity-check every value the user gives you BEFORE you call a tool. If it doesn't look
      right, ask a follow-up question instead of patching nonsense.
      * `author_email`: must look like an email (`x@y.z`). "qwfe" is not an email - ask again.
      * `repository`: must look like a URL (starts with `http://`, `https://`, or `git@`). If
        the user says "no", "none", or "skip", use `https://example.com/TODO` as a clear
        placeholder; never write the literal word "no" into the field.
      * `slug` / `package_name`: derive from `name` if the user hasn't given one. Slugs are
        lowercase-with-hyphens; package names are lowercase_with_underscores.
      * `icon`: a single emoji or a short string. The user says "a basketball" -> "basketball"
        or the basketball emoji. Translate, don't pass through.
      * `agent_id` / `team_id` / `workflow_id`: lowercase-with-hyphens, derived from the name.
      * Lists (workflows, in_scope, etc.) should be concrete sentences, not single words.
    - When the user's answer is too vague to validate (e.g. "ok"), propose a default and ask
      for confirmation instead of guessing.

    Talk like a human, not a Pydantic field
    - NEVER reference internal field paths (`org.author_name`, `ui.app.icon`, etc.) in your
      replies. Ask in plain language: "Who's the author?", "What emoji should the app use?".
    - The user does not need to know the spec schema exists. The spec is a means; the
      conversation is the product.
    - If the user's input is ambiguous or open-ended (e.g. "something like NATO"), interpret
      it ("got it - an international coordination body"), propose concrete values you can
      derive (name, slug, description), and ask for confirmation.
    - If the user's input is short or vague (e.g. "ok", "sure", "go"), advance the interview:
      pick the next placeholder, propose a default, and ask.

    Workflow
    1. Read `placeholders` (and `working_spec` when you need context).
    2. Pick the next field by priority:
       org -> agents -> teams -> workflows -> knowledge -> parameters -> runtime -> ui.
    3. Ask one focused question about that field, using earlier answers for context. When you
       can infer (e.g. slug from name), propose the inferred value and ask for confirmation
       rather than asking cold.
    4. Validate the answer (see the rules above). If invalid, ask again - do not patch.
    5. Apply the matching patch tool, then summarise the change in one short, human sentence.
       After the patch, call `list_placeholders()` if you need an updated view mid-turn.
    6. If the user redirects, apply the requested patch instead and confirm.
    7. Every few turns, prompt: "anything to revise before we continue?"
    8. When `placeholders` is empty AND the user confirms they are happy, ask where the spec
       should be written (default `spec.py`) and call `finalize_spec(path)`.

    Style
    - Be concise. Ask one focused question at a time.
    - After every patch tool call, summarise the change in one short, human sentence.
    - Propose defaults when the user is unsure; do not block on optional fields.
    - Do not narrate tool calls or retries - the UI surfaces them as badges.
    """,
).strip()


QUESTION_TEMPLATES: dict[str, str] = {
    'org.name': "What should we call your organisation?",
    'org.slug': "What slug should we use? (Lowercase-with-hyphens; I can derive it from the name.)",
    'org.package_name': 'What Python package name should we use? (Lowercase_with_underscores.)',
    'org.description': 'In one sentence, what does this organisation do?',
    'org.repository': 'Do you have a git repository URL? If not, say "skip".',
    'org.author_name': "Who's the author or maintainer?",
    'org.author_email': "What's the author's email?",
    'ui.app.name': 'What should the dashboard app be called?',
    'ui.app.icon': 'Pick an emoji or short string for the dashboard icon.',
    'ui.app.description': 'A short tagline for the dashboard?',
    'ui.empty_state.icon': 'An emoji for the empty-state hero?',
    'ui.empty_state.title': 'What headline should the empty state show when there is nothing to display?',
    'ui.empty_state.body': 'What body text should the empty state show?',
    'ui.knowledge_empty': 'What message should the Knowledge tab show when it has no entries yet?',
    'ai.agents': 'What agents does this organisation need? Describe each one in plain language.',
}

PRIORITY_PREFIXES = (
    'org.',
    'ai.agents',
    'ai.teams',
    'ai.workflows',
    'parameters',
    'knowledge',
    'runtime',
    'ui.',
)

ALL_PLACEHOLDERS_FILLED = (
    "Everything's set. Ready to write the spec to disk? Say `finalize` or give me a path."
)


def _working_spec_dependency() -> dict[str, Any]:
    """Live dependency: a JSON-safe snapshot of the working spec, refreshed at every turn."""
    return get_current_spec().model_dump(mode='json')


def _placeholders_dependency() -> list[tuple[str, str]]:
    """Live dependency: fields still holding seed placeholders, refreshed at every turn."""
    return list_placeholders()


def _next_question() -> str:
    """Pick the next placeholder by priority and return its human-friendly question."""
    placeholders = list_placeholders()
    if not placeholders:
        return ALL_PLACEHOLDERS_FILLED

    def sort_key(item: tuple[str, str]) -> tuple[int, str]:
        path = item[0]
        for index, prefix in enumerate(PRIORITY_PREFIXES):
            if path.startswith(prefix):
                return (index, path)
        return (len(PRIORITY_PREFIXES), path)

    next_path = sorted(placeholders, key=sort_key)[0][0]
    return QUESTION_TEMPLATES.get(next_path, 'What should we configure next?')


async def _ensure_response_text(run_output: RunOutput) -> None:
    """Post-hook safety net: if the model ended a turn with no visible text, ask the next question."""
    content = run_output.content
    if content is None or not str(content).strip():
        run_output.content = _next_question()


def build_master_agent() -> Agent:
    """Build the master agent that interviews the user to assemble a spec.py.

    Returns:
        agent: A configured `agno.Agent` carrying every patch tool.
    """
    return Agent(
        id='master',
        name='Master',
        model=os.getenv('AGENTORG_MODEL'),
        instructions=MASTER_INSTRUCTIONS,
        introduction=MASTER_INTRODUCTION,
        db=InMemoryDb(),
        tools=MASTER_TOOLS,
        post_hooks=[_ensure_response_text],
        add_history_to_context=True,
        num_history_runs=20,
        cache_session=True,
        dependencies={
            'working_spec': _working_spec_dependency,
            'placeholders': _placeholders_dependency,
        },
        add_dependencies_to_context=True,
        add_name_to_context=True,
        add_datetime_to_context=True,
        markdown=True,
    )
