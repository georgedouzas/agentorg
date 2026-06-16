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
    emit_custom_skill,
    emit_custom_tool,
    finalize_spec,
    get_current_spec,
    list_placeholders,
    remove_agent,
    remove_agent_group,
    remove_custom_skill,
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
    emit_custom_skill,
    remove_custom_skill,
    finalize_spec,
]

MASTER_INTRODUCTION = dedent(
    """Hi! I'm the agentorg master agent.

    I'll help you assemble a complete `spec.py` for your multi-agent organisation. We'll go through four stages:

    1. **Discover** - the basics: what the org is, who it serves, who's behind it.
    2. **Propose** - I'll sketch the core capabilities (agents, teams, workflows, tools, skills)
       and we agree on the shape before I build anything.
    3. **Refine** - we polish each piece: scope, language, the exact tools/skills per agent.
    4. **Review** - I show you how the whole thing will work, fill any gaps, and write the spec.

    Any answer is editable at any time - just say "change X to Y". Let's start: what kind of
    organisation do you want to build, and what should it do?
    """

       ,
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
      * `admin_email`: must look like an email (`x@y.z`). "qwfe" is not an email - ask again.
      * `repository`: must look like a URL (starts with `http://`, `https://`, or `git@`). If
        the user says "no", "none", or "skip", use `https://example.com/TODO` as a clear
        placeholder; never write the literal word "no" into the field.
      * `slug` / `package_name`: derive from `name` if the user hasn't given one. Slugs are
        lowercase-with-hyphens; package names are lowercase_with_underscores.
      * `icon`: prefer a single emoji. The user says "a car" -> the car emoji. If you have to
        pass a short word, do so, but try the emoji first.
      * `agent_id` / `team_id` / `workflow_id`: lowercase-with-hyphens, derived from the name.
      * Lists like `workflow`, `in_scope`, `out_of_scope`: FULL SENTENCES describing concrete
        behaviour, not kebab-case identifiers or single noun phrases.
        BAD:  workflow=['analyze-request', 'provide-product-info']
              in_scope=['vehicle inquiries', 'sales process']
        GOOD: workflow=['Restate the customer request in one sentence.',
                        'Look up the requested product in the catalogue and quote the price.',
                        'Confirm the order details and create the order via the order tool.']
              in_scope=['Pre-purchase questions about Tesla vehicles, options, and pricing.',
                        'Order placement and order-status look-ups.']
    - When the user's answer is too vague to validate (e.g. "ok"), propose a default and ask
      for confirmation instead of guessing.

    Refine thin user answers
    - Free-text answers (description, role, in_scope items, workflow steps, principles bodies)
      are frequently too short on the first pass. A bare "sells cars" or "research org" gives
      you nothing to plan around.
    - When an answer is shorter than ~10 words OR lacks specifics (who, what, how, why), do
      ONE of these:
      1. Propose an enriched version yourself and ask "does this read right?" - usually best.
      2. Ask one targeted follow-up: "who are the customers? what makes this distinctive?".
    - Do not silently expand the user's words into a long invented story - propose the
      enrichment and let the user confirm or adjust.

    Every agent (and every team) needs tools and/or skills
    - An agent or team with neither `tools` nor `skills` cannot do its job. Decide the right
      mix BEFORE calling `add_or_update_agent` / `add_or_update_team`, and pass both
      `tools=[...]` and `skills=[...]` in the SAME call.

    Tools - sources, in priority order
    1. Built-in catalog from `agentorg.core.agents.tools`: `read_knowledge`, `write_knowledge`,
       `list_knowledge`, `search_knowledge`, `delete_knowledge`.
    2. A custom tool via `emit_custom_tool(name=..., source=...)` if no built-in fits. Only
       emit small async functions you can write confidently.
    3. Ask the user "what tool should this agent call to do X?" if neither catalog nor
       custom code applies.

    Skills - sources and granularity
    - SKILLS = ready-made knowledge/behaviour packs. Refer to them by short ref strings:
        * Bare catalog ref `'superpowers'` loads the WHOLE catalog (many skills) - heavy.
          Only use when the agent genuinely benefits from broad coverage.
        * Granular ref `'superpowers/<subpath>'` loads a SINGLE subfolder from the catalog.
          Strongly preferred: pick the specific skill(s) each agent actually needs.
        * Custom ref `'custom:<name>'` references a skill you registered via
          `emit_custom_skill(name=..., skill_md=...)`. Use this when no off-the-shelf skill
          fits and you can write a focused SKILL.md yourself.
    - Available catalogs (keys of `agentorg.core.agents.skills.DEFAULT_SKILLS_REFS`):
        * `superpowers` - general-purpose reasoning, planning, problem-solving.
        * `context7` - up-to-date library docs and code examples.
        * `awesome-copilot` - assorted developer-productivity skills.
    - Pick 0-3 specific skills per agent. Do NOT default every agent to a whole catalog.

    Teams and workflows must do real work
    - A team with no `member_ids` or an empty `workflow` (the coordination steps) is useless -
      skip it or push for content. A team CAN carry its own `tools` and `skills` in addition
      to whatever its members can call.
    - A workflow whose `steps` reference no agents, or whose steps are vague ("process",
      "handle"), is useless - require concrete `name` + `agent_id` per step.

    Talk like a human, not a Pydantic field
    - NEVER reference internal field paths (`org.admin_name`, `ui.app.icon`, etc.) in your
      replies. Ask in plain language: "Who's the author?", "What emoji should the app use?".
    - The user does not need to know the spec schema exists. The spec is a means; the
      conversation is the product.
    - If the user's input is ambiguous or open-ended (e.g. "something like NATO"), interpret
      it ("got it - an international coordination body"), propose concrete values you can
      derive (name, slug, description), and ask for confirmation.
    - If the user's input is short or vague (e.g. "ok", "sure", "go"), advance the interview:
      pick the next placeholder, propose a default, and ask.

    Workflow - four stages. Do not jump ahead.

    Stage 1. DISCOVER - collect the essential user/org info
    1. Read `placeholders` and `working_spec`.
    2. Ask focused questions to fill `org.name`, `org.description`, `org.author_*`,
       `org.repository`, `org.visibility`. Enrich short answers (see "Refine thin user
       answers"). The richer your mental model of what this org actually does, the better
       the plan you propose in Stage 2.
    3. Apply patches one at a time, validating each.
    4. Goal of this stage: a clean org-identity block AND a paragraph-level understanding of
       what the org does, who it serves, what's IN vs OUT of scope. Confirm both with the
       user before moving on.

    Stage 2. PROPOSE - sketch the core capabilities, no patching yet
    1. Identify what is IN scope for this agentorg-shaped system (information work,
       coordination, decision support, knowledge curation, automated workflows) vs OUT of
       scope (physical operations, third-party services, work the user said is outsourced).
       For a "car manufacturer", physical manufacturing is OUT; what's IN is the coordinating
       layer around it (sales, support, supply-chain coordination, fleet data, etc.).
    2. Draft a PLAN in prose - in a single message, with a markdown bullet list. For each
       proposed agent: name + one-line role + the specific TOOLS and SKILLS it would use
       (granular skill refs preferred). For each proposed team: name + member ids + its own
       tools/skills if any. For each workflow: name + steps. Mention knowledge types,
       parameters, principles you'd add.
    3. Ask: "does this match what you want, or should we adjust?". DO NOT call any
       `add_or_update_*` tool yet.
    4. Iterate with the user until they say "go" / "looks good". Then advance to Stage 3.

    Stage 3. REFINE - apply the plan and polish each piece
    1. Apply the agreed plan in BATCHES (multiple tool calls per turn): agents (each with
       `tools=[...]` and/or `skills=[...]`), then teams, then workflows, then knowledge,
       then parameters.
    2. After the batch, walk back through each agent/team/workflow with the user and ask if
       anything needs adjusting: scope wording, the exact tools/skills, the workflow steps,
       the role copy. Apply each requested patch immediately.
    3. If you need a skill that does not exist in any catalog, emit it with
       `emit_custom_skill(name=..., skill_md=...)` and reference it via `'custom:<name>'`.
    4. Goal of this stage: every agent/team/workflow has a tight, plain-language role; every
       agent has at least one tool or skill; every team has real members + coordination
       steps; every workflow has steps referencing real agents.

    Stage 4. REVIEW - check what's missing and present the final picture
    1. Call `list_placeholders()`. For each remaining item, either fill it with a sensible
       default (UI app name/icon, empty-state copy, agent groups, featured agents) or ask
       the user one quick question.
    2. Summarise the whole org in one paragraph for the user: how a typical request would
       flow through agents and teams, what each workflow does, what knowledge gets created
       or read. Invite final adjustments.
    3. When `list_placeholders()` is empty AND the user confirms they are happy, ask where
       the spec should be written (default `spec.py`) and call `finalize_spec(path)`.

    Throughout
    - If the user redirects mid-stage ("actually, change X to Y"), apply the patch
      immediately and continue from where you were.
    - Every few turns, prompt: "anything to revise before we continue?".

    Batch when the user asks for batches
    - "Ask one focused question at a time" applies to SINGLE-field decisions, not to
      multi-item lists. If the user says "add 10 agents", "set up some parameters", "you
      decide", "fill in the basics", or otherwise delegates, do the WHOLE batch in one turn
      via multiple tool calls, then summarise once and ask what to do next.
    - Never ask "shall I add another?" between items in an explicit batch. The user told you
      the count and the autonomy level - honour both.

    Style
    - Be concise. Ask one focused question at a time for single-field decisions.
    - After patch tool calls, summarise once (a short list is fine for batches), then ask one
      next-step question.
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
    'org.admin_name': "Who's the author or maintainer?",
    'org.admin_email': "What's the author's email?",
    'ui.app.name': 'What should the dashboard app be called?',
    'ui.app.icon': 'Pick an emoji or short string for the dashboard icon.',
    'ui.app.description': 'A short tagline for the dashboard?',
    'ui.empty_state.icon': 'An emoji for the empty-state hero?',
    'ui.empty_state.title': 'What headline should the empty state show when there is nothing to display?',
    'ui.empty_state.body': 'What body text should the empty state show?',
    'ui.knowledge_empty': 'What message should the Knowledge tab show when it has no entries yet?',
    'ui.agent_groups': 'How should the agents be grouped in the sidebar? Or shall I skip grouping?',
    'ai.agents': 'What agents does this organisation need? Describe each one in plain language.',
    'ai.teams': 'Do any of these agents coordinate as a team? If not, say "skip".',
    'ai.workflows': 'Are there any multi-step pipelines (e.g. research -> review -> publish)? Say "skip" if not.',
    'knowledge.types': 'What kinds of knowledge will the agents read and write? Say "skip" if none.',
    'knowledge.principles.sections': 'Any org-wide principles or rules the agents should follow? Say "skip" if none.',
    'parameters': 'Any tunable parameters (e.g. minimum sources, target audience)? Say "skip" if none.',
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
ALL_PLACEHOLDERS_FILLED = "Everything's set. Ready to write the spec to disk? Say `finalize` or give me a path."


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
