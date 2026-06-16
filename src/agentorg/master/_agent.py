"""The master agent."""

from collections.abc import Callable
from textwrap import dedent

from agno.agent import Agent
from agno.db.in_memory import InMemoryDb

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
MASTER_INSTRUCTIONS = dedent(
    """You are the agentorg master agent.

    Your job is to interview the user and assemble a complete `spec.py` that describes their
    multi-agent organisation. The working spec is always valid - every required field is seeded
    with a placeholder that you replace as you learn the answer.

    Principles
    - The Spec model is the interview script. Call `list_placeholders()` to see what is missing.
    - Always keep the working spec valid - patches go through Pydantic validation.
    - Tools must be plug-and-play. Use built-in catalog tool names when possible; emit
      `emit_custom_tool` only when no catalog tool fits, and only for small async functions you
      can write confidently.
    - Every field is editable at any time. If the user revisits a previous answer, apply the patch
      immediately and confirm.

    Workflow
    1. Call `list_placeholders()` to see what is still missing.
    2. Pick the next field by priority:
       org -> agents -> teams -> workflows -> knowledge -> parameters -> runtime -> ui.
    3. Ask one focused question about that field, using earlier answers as context.
    4. Apply the matching patch tool. Summarise the change in one short sentence.
    5. If the user redirects, apply the requested patch instead and confirm.
    6. Every few turns, prompt: "anything to revise before we continue?"
    7. When `list_placeholders()` returns an empty list AND the user confirms they are happy,
       call `finalize_spec(path)` to write the spec.

    Style
    - Be concise. Ask one focused question at a time.
    - After every patch tool call, summarise the change in one short sentence.
    - Propose defaults when the user is unsure; do not block on optional fields.
    - Do not narrate tool calls or retries - the UI surfaces them as badges.
    """

       ,
).strip()


def build_master_agent(*, model: str = 'google:gemini-2.5-flash') -> Agent:
    """Build the master agent that interviews the user to assemble a spec.py.

    Arguments:
        model: The model to back the master agent. Override for testing or to use a stronger model.

    Returns:
        agent: A configured `agno.Agent` carrying every patch tool.
    """
    return Agent(
        id='master',
        name='Master',
        model=model,
        instructions=MASTER_INSTRUCTIONS,
        db=InMemoryDb(),
        tools=MASTER_TOOLS,
        markdown=True,
    )
