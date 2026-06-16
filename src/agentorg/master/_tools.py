"""Patch tools the master agent calls to update the working spec."""

from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel

from agentorg.core.spec import (
    AI,
    AppUI,
    EmptyState,
    EnvVar,
    EnvVars,
    GroupRef,
    Infra,
    Knowledge,
    KnowledgeType,
    KnowledgeTypeMetadataField,
    Org,
    OverviewBlock,
    Parameter,
    Principles,
    PrincipleSection,
    Runtime,
    SetupStep,
    Spec,
)

from ._models import AgentSpec, CustomTool, StepSpec, TeamSpec, WorkflowSpec
from ._sandbox import ToolValidationError, validate_tool_source
from ._seed import PLACEHOLDER_VALUES
from ._state import get_state
from ._writer import write_spec

ItemT = TypeVar('ItemT', bound=BaseModel)


def _is_placeholder(value: object) -> bool:
    """Return True when `value` is a placeholder string seeded by `default_spec`."""
    return isinstance(value, str) and value in PLACEHOLDER_VALUES


def _upsert(items: list[ItemT], key_field: str, key_value: object, new_item: ItemT) -> tuple[list[ItemT], bool]:
    """Insert or replace an item identified by `key_field`.

    Returns the new list + whether it existed before.
    """
    existed = any(getattr(i, key_field) == key_value for i in items)
    new_items = [i for i in items if getattr(i, key_field) != key_value]
    new_items.append(new_item)
    return new_items, existed


def _remove(items: list[ItemT], key_field: str, key_value: object) -> tuple[list[ItemT], bool]:
    """Drop the item identified by `key_field`.

    Returns the new list + whether it was present.
    """
    new_items = [i for i in items if getattr(i, key_field) != key_value]
    return new_items, len(new_items) != len(items)


def _replace_ai(
    *,
    agents: list[object] | None = None,
    teams: list[object] | None = None,
    workflows: list[object] | None = None,
) -> None:
    """Replace `spec.ai` with a new `AI` carrying the updated lists (only changed lists are passed)."""
    state = get_state()
    ai = state.spec.ai
    state.spec.ai = AI(
        framework=ai.framework,
        agents=agents if agents is not None else list(ai.agents),
        teams=teams if teams is not None else list(ai.teams),
        workflows=workflows if workflows is not None else list(ai.workflows),
    )


def list_placeholders() -> list[tuple[str, str]]:
    """List the fields in the working spec that still hold seed placeholders.

    Returns:
        items: `(field_path, current_value)` tuples for each unfilled field, plus `('ai.agents', '(empty)')`
            when no user agents have been declared yet.
    """
    spec = get_state().spec
    placeholders: list[tuple[str, str]] = []
    for fld in ('name', 'slug', 'package_name', 'description', 'repository', 'author_name', 'author_email'):
        value = getattr(spec.org, fld)
        if _is_placeholder(value):
            placeholders.append((f'org.{fld}', value))
    for fld, value in (
        ('ui.app.name', spec.ui.app.name),
        ('ui.app.icon', spec.ui.app.icon),
        ('ui.app.description', spec.ui.app.description),
        ('ui.empty_state.icon', spec.ui.empty_state.icon),
        ('ui.empty_state.title', spec.ui.empty_state.title),
        ('ui.empty_state.body', spec.ui.empty_state.body),
        ('ui.knowledge_empty', spec.ui.knowledge_empty),
    ):
        if _is_placeholder(value):
            placeholders.append((fld, value))
    if not spec.ai.agents:
        placeholders.append(('ai.agents', '(empty)'))
    return placeholders


def set_org_identity(
    *,
    name: str | None = None,
    slug: str | None = None,
    package_name: str | None = None,
    description: str | None = None,
    repository: str | None = None,
    author_name: str | None = None,
    author_email: str | None = None,
    visibility: Literal['public', 'private'] | None = None,
) -> str:
    """Update fields on `spec.org`.

    Only provided arguments are changed.

    Arguments:
            name: Display name.
            slug: URL-safe identifier.
            package_name: Python package name.
            description: One-line description.
            repository: Git repository URL.
            author_name: Author name.
            author_email: Author email.
            visibility: `public` or `private`.

    Returns:
            message: Confirmation listing the fields that changed.
    """
    state = get_state()
    updates = {
        'name': name,
        'slug': slug,
        'package_name': package_name,
        'description': description,
        'repository': repository,
        'author_name': author_name,
        'author_email': author_email,
        'visibility': visibility,
    }
    changed = {k: v for k, v in updates.items() if v is not None}
    if not changed:
        return 'No changes - all arguments were omitted.'
    state.spec.org = Org(**{**state.spec.org.model_dump(), **changed})
    return f"Updated org fields: {', '.join(sorted(changed))}."


def add_or_update_agent(
    *,
    agent_id: str,
    name: str,
    role: str,
    in_scope: list[str],
    workflow: list[str],
    tools: list[str] | None = None,
    model: str = 'google:gemini-2.5-flash',
    when_to_act: list[str] | None = None,
    out_of_scope: list[str] | None = None,
    style: list[str] | None = None,
    principles: list[str] | None = None,
    introduction: str = '',
    description: str = '',
    additional_context: str = '',
) -> str:
    """Add or update a user-defined agent.

    Arguments:
        agent_id: Stable identifier; matching an existing agent triggers an update.
        name: Display name.
        role: One-line description of the agent's responsibility.
        in_scope: Topics the agent owns.
        workflow: Steps the agent follows for an in-scope request.
        tools: Names of built-in or custom tools the agent uses.
        model: Model the agent runs on.
        when_to_act: Rules for when the agent engages.
        out_of_scope: Topics the agent declines.
        style: Tone and format rules.
        principles: Org-wide rules the agent follows.
        introduction: Greeting on first turn.
        description: Description of the agent.
        additional_context: Extra context for the system prompt.

    Returns:
        message: `Added` or `Updated` confirmation.
    """
    spec = AgentSpec(
        agent_id=agent_id,
        name=name,
        role=role,
        model=model,
        tools=tools or [],
        in_scope=in_scope,
        workflow=workflow,
        when_to_act=when_to_act or [],
        out_of_scope=out_of_scope or [],
        style=style or [],
        principles=principles or [],
        introduction=introduction,
        description=description,
        additional_context=additional_context,
    )
    new_agents, existed = _upsert(list(get_state().spec.ai.agents), 'agent_id', agent_id, spec)
    _replace_ai(agents=new_agents)
    return f"{'Updated' if existed else 'Added'} agent '{agent_id}'."


def remove_agent(agent_id: str) -> str:
    """Remove the agent with the given `agent_id`.

    Arguments:
        agent_id: Stable identifier of the agent to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    new_agents, removed = _remove(list(get_state().spec.ai.agents), 'agent_id', agent_id)
    if not removed:
        return f"No agent named '{agent_id}'."
    _replace_ai(agents=new_agents)
    return f"Removed agent '{agent_id}'."


def add_or_update_team(
    *,
    team_id: str,
    name: str,
    role: str,
    workflow: list[str],
    member_ids: list[str],
    mode: Literal['coordinate', 'route', 'broadcast', 'tasks'] = 'coordinate',
    model: str = 'google:gemini-2.5-flash',
    in_scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
    when_to_act: list[str] | None = None,
    style: list[str] | None = None,
    principles: list[str] | None = None,
    introduction: str = '',
    description: str = '',
    additional_context: str = '',
) -> str:
    """Add or update a team that coordinates existing agents.

    Arguments:
        team_id: Stable identifier; matching an existing team triggers an update.
        name: Display name.
        role: One-line description of the team's responsibility.
        workflow: Steps the team follows when coordinating its members.
        member_ids: `agent_id`s of the team's members.
        mode: Coordination mode.
        model: Model the team's orchestrator runs on.
        in_scope: Topics the team handles.
        out_of_scope: Topics the team declines.
        when_to_act: Rules for when the team engages.
        style: Tone and format rules.
        principles: Org-wide rules the team follows.
        introduction: Greeting on first turn.
        description: Description of the team.
        additional_context: Extra context for the system prompt.

    Returns:
        message: `Added` or `Updated` confirmation.
    """
    spec = TeamSpec(
        team_id=team_id,
        name=name,
        role=role,
        model=model,
        member_ids=member_ids,
        mode=mode,
        workflow=workflow,
        in_scope=in_scope or [],
        out_of_scope=out_of_scope or [],
        when_to_act=when_to_act or [],
        style=style or [],
        principles=principles or [],
        introduction=introduction,
        description=description,
        additional_context=additional_context,
    )
    new_teams, existed = _upsert(list(get_state().spec.ai.teams), 'team_id', team_id, spec)
    _replace_ai(teams=new_teams)
    return f"{'Updated' if existed else 'Added'} team '{team_id}'."


def remove_team(team_id: str) -> str:
    """Remove the team with the given `team_id`.

    Arguments:
        team_id: Stable identifier of the team to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    new_teams, removed = _remove(list(get_state().spec.ai.teams), 'team_id', team_id)
    if not removed:
        return f"No team named '{team_id}'."
    _replace_ai(teams=new_teams)
    return f"Removed team '{team_id}'."


def add_or_update_workflow(
    *,
    workflow_id: str,
    name: str,
    steps: list[dict],
    description: str = '',
) -> str:
    """Add or update a workflow defined by an ordered list of steps.

    Arguments:
        workflow_id: Stable identifier; matching an existing workflow triggers an update.
        name: Display name.
        steps: A list of step dicts; each requires `name` and `agent_id`, optionally `requires_output_review`.
        description: Optional description of what the workflow does.

    Returns:
        message: `Added` or `Updated` confirmation.
    """
    step_specs = [StepSpec(**s) for s in steps]
    spec = WorkflowSpec(workflow_id=workflow_id, name=name, steps=step_specs, description=description)
    new_workflows, existed = _upsert(list(get_state().spec.ai.workflows), 'workflow_id', workflow_id, spec)
    _replace_ai(workflows=new_workflows)
    return f"{'Updated' if existed else 'Added'} workflow '{workflow_id}'."


def remove_workflow(workflow_id: str) -> str:
    """Remove the workflow with the given `workflow_id`.

    Arguments:
        workflow_id: Stable identifier of the workflow to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    new_workflows, removed = _remove(list(get_state().spec.ai.workflows), 'workflow_id', workflow_id)
    if not removed:
        return f"No workflow named '{workflow_id}'."
    _replace_ai(workflows=new_workflows)
    return f"Removed workflow '{workflow_id}'."


def add_or_update_parameter(
    *,
    name: str,
    param_type: Literal['int', 'float', 'string', 'bool', 'object', 'array'],
    default: object,
    label: str,
    display_format: str | None = None,
) -> str:
    """Add or update an org-level parameter (a tunable knob referenced from principles or agents).

    Arguments:
        name: Stable identifier; matching an existing parameter triggers an update.
        param_type: Parameter type.
        default: Default value.
        label: Display label.
        display_format: Optional UI format hint (e.g. `'markdown'`).

    Returns:
        message: `Added` or `Updated` confirmation.
    """
    state = get_state()
    new_param = Parameter(name=name, type=param_type, default=default, label=label, format=display_format)
    new_params, existed = _upsert(list(state.spec.parameters), 'name', name, new_param)
    state.spec.parameters = new_params
    return f"{'Updated' if existed else 'Added'} parameter '{name}'."


def remove_parameter(name: str) -> str:
    """Remove the parameter with the given `name`.

    Arguments:
        name: Stable identifier of the parameter to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    state = get_state()
    new_params, removed = _remove(list(state.spec.parameters), 'name', name)
    if not removed:
        return f"No parameter named '{name}'."
    state.spec.parameters = new_params
    return f"Removed parameter '{name}'."


def add_or_update_knowledge_type(
    *,
    knowledge_type_id: str,
    label: str,
    metadata_fields: list[dict] | None = None,
) -> str:
    """Add or update a knowledge type the org's agents read and write.

    Arguments:
        knowledge_type_id: Stable identifier; matching an existing type triggers an update.
        label: Display label.
        metadata_fields: Optional list of `{name, type}` dicts describing per-unit metadata.

    Returns:
        message: `Added` or `Updated` confirmation.
    """
    state = get_state()
    fields = [KnowledgeTypeMetadataField(**f) for f in (metadata_fields or [])]
    new_type = KnowledgeType(id=knowledge_type_id, label=label, metadata_fields=fields)
    new_types, existed = _upsert(list(state.spec.knowledge.types), 'id', knowledge_type_id, new_type)
    state.spec.knowledge = Knowledge(principles=state.spec.knowledge.principles, types=new_types)
    return f"{'Updated' if existed else 'Added'} knowledge type '{knowledge_type_id}'."


def remove_knowledge_type(knowledge_type_id: str) -> str:
    """Remove the knowledge type with the given `knowledge_type_id`.

    Arguments:
        knowledge_type_id: Stable identifier of the type to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    state = get_state()
    new_types, removed = _remove(list(state.spec.knowledge.types), 'id', knowledge_type_id)
    if not removed:
        return f"No knowledge type named '{knowledge_type_id}'."
    state.spec.knowledge = Knowledge(principles=state.spec.knowledge.principles, types=new_types)
    return f"Removed knowledge type '{knowledge_type_id}'."


def add_or_update_principle_section(*, section_id: str, title: str, body: str) -> str:
    """Add or update one section of the org's principles.

    Arguments:
        section_id: Stable identifier; matching an existing section triggers an update.
        title: Section heading.
        body: Markdown body, may reference parameters as `{param_name}`.

    Returns:
        message: `Added` or `Updated` confirmation.
    """
    state = get_state()
    section = PrincipleSection(id=section_id, title=title, body=body)
    new_sections, existed = _upsert(list(state.spec.knowledge.principles.sections), 'id', section_id, section)
    state.spec.knowledge = Knowledge(
        principles=Principles(sections=new_sections),
        types=state.spec.knowledge.types,
    )
    return f"{'Updated' if existed else 'Added'} principle section '{section_id}'."


def remove_principle_section(section_id: str) -> str:
    """Remove the principle section with the given `section_id`.

    Arguments:
        section_id: Stable identifier of the section to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    state = get_state()
    new_sections, removed = _remove(list(state.spec.knowledge.principles.sections), 'id', section_id)
    if not removed:
        return f"No principle section named '{section_id}'."
    state.spec.knowledge = Knowledge(
        principles=Principles(sections=new_sections),
        types=state.spec.knowledge.types,
    )
    return f"Removed principle section '{section_id}'."


def set_runtime_infra(
    *,
    packaging: Literal['none', 'docker'] | None = None,
    database: Literal['sqlite', 'postgres'] | None = None,
    vector_db: Literal['chromadb', 'pgvector'] | None = None,
    embedder: str | None = None,
    api: Literal['none', 'railway'] | None = None,
    frontend: Literal['none', 'vercel'] | None = None,
    auth: Literal['none', 'clerk'] | None = None,
) -> str:
    """Update fields on `spec.runtime.infra`.

    Only provided arguments are changed.

    Arguments:
            packaging: `none` or `docker`.
            database: `sqlite` or `postgres`.
            vector_db: `chromadb` or `pgvector`.
            embedder: `provider:model` pair.
            api: `none` or `railway`.
            frontend: `none` or `vercel`.
            auth: `none` or `clerk`.

    Returns:
            message: Confirmation listing the fields that changed.
    """
    state = get_state()
    updates = {
        'packaging': packaging,
        'database': database,
        'vector_db': vector_db,
        'embedder': embedder,
        'api': api,
        'frontend': frontend,
        'auth': auth,
    }
    changed = {k: v for k, v in updates.items() if v is not None}
    if not changed:
        return 'No changes - all arguments were omitted.'
    state.spec.runtime = Runtime(
        infra=Infra(**{**state.spec.runtime.infra.model_dump(), **changed}),
        env_vars=state.spec.runtime.env_vars,
        setup=state.spec.runtime.setup,
    )
    return f"Updated runtime.infra fields: {', '.join(sorted(changed))}."


def add_or_update_env_var(*, name: str, description: str, required_label: str, required: bool) -> str:
    """Add or update an environment variable the rendered org declares.

    Arguments:
        name: Variable name (e.g. `GOOGLE_API_KEY`).
        description: One-line description shown in the setup checklist.
        required_label: Display label (e.g. `'Prod'`, `'Dev'`).
        required: True for required vars, False for optional.

    Returns:
        message: `Added` or `Updated` confirmation.
    """
    state = get_state()
    env = state.spec.runtime.env_vars
    new_var = EnvVar(name=name, description=description, required_label=required_label)
    target_list = list(env.required if required else env.optional)
    other_list = list(env.optional if required else env.required)
    new_target, existed = _upsert(target_list, 'name', name, new_var)
    other_filtered = [v for v in other_list if v.name != name]
    state.spec.runtime = Runtime(
        infra=state.spec.runtime.infra,
        env_vars=EnvVars(
            required=new_target if required else other_filtered,
            optional=other_filtered if required else new_target,
        ),
        setup=state.spec.runtime.setup,
    )
    return f"{'Updated' if existed else 'Added'} env var '{name}' ({'required' if required else 'optional'})."


def remove_env_var(name: str) -> str:
    """Remove the env var with the given `name` from both required and optional lists.

    Arguments:
        name: Variable name to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    state = get_state()
    env = state.spec.runtime.env_vars
    new_required, removed_r = _remove(list(env.required), 'name', name)
    new_optional, removed_o = _remove(list(env.optional), 'name', name)
    if not (removed_r or removed_o):
        return f"No env var named '{name}'."
    state.spec.runtime = Runtime(
        infra=state.spec.runtime.infra,
        env_vars=EnvVars(required=new_required, optional=new_optional),
        setup=state.spec.runtime.setup,
    )
    return f"Removed env var '{name}'."


def add_or_update_setup_step(*, step_id: str, title: str, description: str, variables: list[str]) -> str:
    """Add or update one step on the post-install setup checklist.

    Arguments:
        step_id: Stable identifier; matching an existing step triggers an update.
        title: Step title.
        description: Markdown body explaining what to do.
        variables: Env var names this step configures (used for completion tracking).

    Returns:
        message: `Added` or `Updated` confirmation.
    """
    state = get_state()
    step = SetupStep(id=step_id, title=title, description=description, variables=variables)
    new_steps, existed = _upsert(list(state.spec.runtime.setup), 'id', step_id, step)
    state.spec.runtime = Runtime(
        infra=state.spec.runtime.infra,
        env_vars=state.spec.runtime.env_vars,
        setup=new_steps,
    )
    return f"{'Updated' if existed else 'Added'} setup step '{step_id}'."


def remove_setup_step(step_id: str) -> str:
    """Remove the setup step with the given `step_id`.

    Arguments:
        step_id: Stable identifier of the step to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    state = get_state()
    new_steps, removed = _remove(list(state.spec.runtime.setup), 'id', step_id)
    if not removed:
        return f"No setup step named '{step_id}'."
    state.spec.runtime = Runtime(
        infra=state.spec.runtime.infra,
        env_vars=state.spec.runtime.env_vars,
        setup=new_steps,
    )
    return f"Removed setup step '{id}'."


def _replace_ui(**changes: object) -> None:
    """Replace `spec.ui` carrying the supplied field overrides on top of the current UI."""
    state = get_state()
    state.spec.ui = type(state.spec.ui)(**{**state.spec.ui.model_dump(), **changes})


def set_ui_app(*, name: str | None = None, icon: str | None = None, description: str | None = None) -> str:
    """Update `spec.ui.app`.

    Only provided arguments are changed.

    Arguments:
            name: App display name.
            icon: Single emoji or short string.
            description: One-line app description.

    Returns:
            message: Confirmation listing the fields that changed.
    """
    state = get_state()
    updates = {k: v for k, v in {'name': name, 'icon': icon, 'description': description}.items() if v is not None}
    if not updates:
        return 'No changes - all arguments were omitted.'
    new_app = AppUI(**{**state.spec.ui.app.model_dump(), **updates})
    state.spec.ui = type(state.spec.ui)(**{**state.spec.ui.model_dump(), 'app': new_app})
    return f"Updated ui.app fields: {', '.join(sorted(updates))}."


def set_ui_empty_state(*, icon: str | None = None, title: str | None = None, body: str | None = None) -> str:
    """Update `spec.ui.empty_state`.

    Only provided arguments are changed.

    Arguments:
            icon: Single emoji or short string.
            title: Bold heading copy.
            body: Body copy under the title.

    Returns:
            message: Confirmation listing the fields that changed.
    """
    state = get_state()
    updates = {k: v for k, v in {'icon': icon, 'title': title, 'body': body}.items() if v is not None}
    if not updates:
        return 'No changes - all arguments were omitted.'
    new_empty = EmptyState(**{**state.spec.ui.empty_state.model_dump(), **updates})
    state.spec.ui = type(state.spec.ui)(**{**state.spec.ui.model_dump(), 'empty_state': new_empty})
    return f"Updated ui.empty_state fields: {', '.join(sorted(updates))}."


def set_knowledge_empty(text: str) -> str:
    """Set the copy shown when no knowledge units exist yet.

    Arguments:
        text: A short message guiding the user to populate knowledge.

    Returns:
        message: Confirmation.
    """
    _replace_ui(knowledge_empty=text)
    return 'Updated ui.knowledge_empty.'


def add_or_update_agent_group(*, label: str, ids: list[str]) -> str:
    """Add or update a sidebar group listing agents by id.

    Arguments:
        label: Group header.
        ids: `agent_id`s in display order.

    Returns:
        message: `Added` or `Updated` confirmation.
    """
    state = get_state()
    group = GroupRef(label=label, ids=ids)
    new_groups, existed = _upsert(list(state.spec.ui.agent_groups), 'label', label, group)
    _replace_ui(agent_groups=[g.model_dump() for g in new_groups])
    return f"{'Updated' if existed else 'Added'} agent group '{label}'."


def remove_agent_group(label: str) -> str:
    """Remove the agent group with the given `label`.

    Arguments:
        label: Group header to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    state = get_state()
    new_groups, removed = _remove(list(state.spec.ui.agent_groups), 'label', label)
    if not removed:
        return f"No agent group labelled '{label}'."
    _replace_ui(agent_groups=[g.model_dump() for g in new_groups])
    return f"Removed agent group '{label}'."


def set_featured_agents(ids: list[str]) -> str:
    """Set the list of featured agents shown prominently in the UI.

    Arguments:
        ids: `agent_id`s to feature.

    Returns:
        message: Confirmation.
    """
    _replace_ui(featured_agents=ids)
    return f'Featured agents: {", ".join(ids) if ids else "(none)"}.'


def set_agent_icons(icons: dict[str, str]) -> str:
    """Set the `agent_id -> icon` map.

    Arguments:
        icons: Map from `agent_id` to a short string / emoji.

    Returns:
        message: Confirmation.
    """
    _replace_ui(agent_icons=icons)
    return f'Set icons for {len(icons)} agent(s).'


def add_or_update_overview_block(*, title: str, body: str) -> str:
    """Add or update a markdown card rendered on the Overview tab.

    Arguments:
        title: Card heading.
        body: Card body markdown.

    Returns:
        message: `Added` or `Updated` confirmation.
    """
    state = get_state()
    block = OverviewBlock(title=title, body=body)
    new_blocks, existed = _upsert(list(state.spec.ui.overview), 'title', title, block)
    _replace_ui(overview=[b.model_dump() for b in new_blocks])
    return f"{'Updated' if existed else 'Added'} overview block '{title}'."


def remove_overview_block(title: str) -> str:
    """Remove the overview block with the given `title`.

    Arguments:
        title: Card heading to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    state = get_state()
    new_blocks, removed = _remove(list(state.spec.ui.overview), 'title', title)
    if not removed:
        return f"No overview block titled '{title}'."
    _replace_ui(overview=[b.model_dump() for b in new_blocks])
    return f"Removed overview block '{title}'."


def emit_custom_tool(*, name: str, source: str) -> str:
    """Validate and register a user-defined async tool function.

    The `source` must define a top-level `async def <name>(...)` returning a string. It is
    validated in a subprocess sandbox: the source is imported with a hard timeout, and the named
    function must be a coroutine function. On success the tool is stored in state and becomes
    available to `add_or_update_agent(tools=[...])`.

    Arguments:
        name: The function name that must appear in `source` as `async def <name>(...)`.
        source: Complete Python source code defining the function (and any imports it needs).

    Returns:
        message: `Registered` or `Updated` confirmation, or a validation-error description.
    """
    try:
        validate_tool_source(name, source)
    except ToolValidationError as exc:
        return f"Validation failed for '{name}': {exc}"
    state = get_state()
    new_tools, existed = _upsert(list(state.custom_tools), 'name', name, CustomTool(name=name, source=source))
    state.custom_tools = new_tools
    return f"{'Updated' if existed else 'Registered'} custom tool '{name}'."


def remove_custom_tool(name: str) -> str:
    """Remove the custom tool with the given `name`.

    Arguments:
        name: Name of the tool to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    state = get_state()
    new_tools, removed = _remove(list(state.custom_tools), 'name', name)
    if not removed:
        return f"No custom tool named '{name}'."
    state.custom_tools = new_tools
    return f"Removed custom tool '{name}'."


def get_current_spec() -> Spec:
    """Return the working spec.

    Returns:
        spec: The current in-memory `Spec`.
    """
    return get_state().spec


def finalize_spec(output_path: str | Path) -> str:
    """Render the working spec to a `spec.py` file at `output_path`.

    Arguments:
        output_path: Destination file path. Parent directories are created if missing.

    Returns:
        message: Absolute path of the file written.
    """
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    write_spec(get_state().spec, target, custom_tools=get_state().custom_tools)
    return f'Wrote {target}.'
