"""Patch tools the master agent calls to update the working spec."""

import re
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from ..core.spec import (
    Agent,
    AppUI,
    EmptyState,
    EnvVar,
    EnvVars,
    GroupRef,
    Infra,
    Knowledge,
    KnowledgeType,
    KnowledgeTypeMetadataField,
    Operations,
    Org,
    OverviewBlock,
    Parameter,
    Principles,
    PrincipleSection,
    Runtime,
    SetupStep,
    Spec,
)
from ._models import CustomSkill, CustomTool, UnitDraft
from ._sandbox import (
    SkillValidationError,
    ToolValidationError,
    compile_tool,
    validate_skill_source,
    validate_tool_source,
)
from ._seed import PLACEHOLDER_VALUES
from ._stages import STAGE_LABELS, STAGES, advance
from ._state import Discovery, get_state
from ._structure import assemble_ai
from ._writer import render_spec, write_spec

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


def _org_placeholders(spec: Spec) -> list[tuple[str, str]]:
    """Return placeholder entries for the seed-valued fields on `spec.org`."""
    fields = ('name', 'slug', 'package_name', 'description', 'repository', 'admin_name', 'admin_email')
    return [(f'org.{f}', getattr(spec.org, f)) for f in fields if _is_placeholder(getattr(spec.org, f))]


def _ai_placeholders(spec: Spec) -> list[tuple[str, str]]:
    """Return placeholder entries for an org without agents and for agents without any tools."""
    out: list[tuple[str, str]] = []
    if not spec.ai.agents:
        out.append(('ai.agents', '(empty)'))
    for agent in spec.ai.agents:
        if not agent.tools and not agent.mcp_servers and not agent.skills:
            out.append((f'ai.agents[{agent.id}].tools', '(builtin only)'))
    return out


def _ui_placeholders(spec: Spec) -> list[tuple[str, str]]:
    """Return placeholder entries for seed-valued UI fields + empty UI collections."""
    out: list[tuple[str, str]] = []
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
            out.append((fld, value))
    if not spec.ui.agent_groups:
        out.append(('ui.agent_groups', '(empty)'))
    return out


def list_placeholders() -> list[tuple[str, str]]:
    """List fields and sections the master still needs to confirm with the user.

    Two kinds of items show up: (a) required fields still holding their TODO placeholder string,
    and (b) optional collections that are still empty (no agents/teams/workflows/parameters/
    knowledge/principles/UI groups, plus agents with no tools attached). The master treats both
    as "ask the user about this before finalising"; an explicit "leave empty" answer is still
    a turn that needs to happen.

    Returns:
        items: `(field_path, current_value)` tuples in interview-priority order.
    """
    spec = get_state().spec
    out: list[tuple[str, str]] = []
    out.extend(_org_placeholders(spec))
    out.extend(_ai_placeholders(spec))
    if not spec.knowledge.types:
        out.append(('knowledge.types', '(empty)'))
    if not spec.knowledge.principles.sections:
        out.append(('knowledge.principles.sections', '(empty)'))
    if not spec.parameters:
        out.append(('parameters', '(empty)'))
    out.extend(_ui_placeholders(spec))
    return out


def _is_valid_email(value: str) -> bool:
    return bool(re.match(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$', value))


def _is_valid_repository(value: str) -> bool:
    """Validate a repository URL; recognise the seed placeholder and `https://example.com/TODO`."""
    if value in PLACEHOLDER_VALUES or value.endswith('/TODO'):
        return True
    https_re = r'^https?://[A-Za-z0-9.\-]+(?::\d+)?(?:/[^/\s]+)+/?$'
    ssh_re = r'^git@[A-Za-z0-9.\-]+:[^/\s][^/\s]*/[^/\s]+(?:\.git)?$'
    return bool(re.match(https_re, value) or re.match(ssh_re, value))


def set_org_identity(
    *,
    name: str | None = None,
    slug: str | None = None,
    package_name: str | None = None,
    description: str | None = None,
    repository: str | None = None,
    admin_name: str | None = None,
    admin_email: str | None = None,
    visibility: Literal['public', 'private'] | None = None,
) -> str:
    """Update fields on `spec.org`.

    Only provided arguments are changed. `repository` must be an `http(s)` or `git@` URL (the
    seed placeholder and `https://example.com/TODO` are accepted); `admin_email` must look
    like an email.

    Arguments:
        name: Display name.
        slug: URL-safe identifier.
        package_name: Python package name.
        description: One-line description.
        repository: Git repository URL.
        admin_name: Admin / maintainer name.
        admin_email: Admin / maintainer email.
        visibility: `public` or `private`.

    Returns:
        message: Confirmation listing the fields that changed, or a validation-error
            description if a value was rejected.
    """
    if repository is not None and not _is_valid_repository(repository):
        return (
            f"Repository URL {repository!r} doesn't look right. Expected an http(s):// or git@ URL "
            f"like 'https://github.com/owner/repo' or 'git@github.com:owner/repo.git'. "
            f"Use 'https://example.com/TODO' if the user wants to skip it."
        )
    if admin_email is not None and not _is_valid_email(admin_email):
        return f"Admin email {admin_email!r} doesn't look like an email. Ask the user again (format: name@host.tld)."

    desc_gate = _check_description_length(description)
    if desc_gate is not None:
        return desc_gate

    state = get_state()
    updates = {
        'name': name,
        'slug': slug,
        'package_name': package_name,
        'description': description,
        'repository': repository,
        'admin_name': admin_name,
        'admin_email': admin_email,
        'visibility': visibility,
    }
    changed = {k: v for k, v in updates.items() if v is not None}
    if not changed:
        return 'No changes - all arguments were omitted.'
    state.spec.org = Org(**{**state.spec.org.model_dump(), **changed})

    # Cascade name → ui.app.name when the dashboard header is still at its seed default.
    # Without this, the user sets the org name but the rendered dashboard keeps showing
    # "Untitled org" because `app_name` reads from `ui.app.name`, not `org.name`. We only
    # cascade when ui.app.name is still a placeholder so we don't trample explicit choices.
    if 'name' in changed and _is_placeholder(state.spec.ui.app.name):
        state.spec.ui = state.spec.ui.model_copy(
            update={
                'app': state.spec.ui.app.model_copy(update={'name': changed['name']}),
            },
        )

    return f"Updated org fields: {', '.join(sorted(changed))}."


def _first_error(error: ValidationError | ValueError) -> str:
    """Return a short description of a validation error."""
    if isinstance(error, ValidationError):
        return '; '.join(f"{'.'.join(str(p) for p in e['loc']) or 'value'}: {e['msg']}" for e in error.errors()[:3])
    return str(error)


def _rebuild_spec(**changes: Any) -> str | None:  # noqa: ANN401
    """Replace spec fields with `changes` when the whole spec still validates; return the error otherwise."""
    state = get_state()
    fields = {name: getattr(state.spec, name) for name in Spec.model_fields}
    try:
        state.spec = Spec(**{**fields, **changes})
    except (ValidationError, ValueError) as error:
        return _first_error(error)
    return None


def _sync_structure() -> str:
    """Assemble the agent and unit drafts into the spec and describe whether the structure is complete."""
    state = get_state()
    try:
        ai = assemble_ai(state.agents, state.units)
    except (ValidationError, ValueError) as error:
        state.structure_error = _first_error(error)
        return f'The structure is not complete yet: {state.structure_error}'
    problem = _rebuild_spec(ai=ai)
    state.structure_error = problem
    if problem is not None:
        return f'The spec does not validate: {problem}'
    return 'The org structure is valid and live in the preview.'


def _unit(unit_id: str) -> UnitDraft | None:
    """Return the unit draft with id `unit_id`, or None."""
    return next((unit for unit in get_state().units if unit.id == unit_id), None)


def _detach(member_id: str) -> None:
    """Remove `member_id` from every unit's members and lead slot."""
    for unit in get_state().units:
        if member_id in unit.members:
            unit.members.remove(member_id)
        if unit.lead == member_id:
            unit.lead = None


def add_or_update_unit(
    *,
    unit_id: str,
    name: str,
    model: Literal['solo', 'pipeline', 'hub', 'pool', 'council'],
    parent_id: str | None = None,
    routing: Literal['round_robin', 'least_loaded', 'skill_match'] = 'least_loaded',
    decision: Literal['majority', 'judge', 'unanimous'] | None = None,
    owners: list[str] | None = None,
    max_autonomy: Literal['read_only', 'propose', 'act', 'autonomous'] | None = None,
    monthly_usd: float | None = None,
    approval_required: list[str] | None = None,
) -> str:
    """Add or update a unit of the org; its agents join with `add_or_update_agent(unit_id=...)`.

    Models: `solo` (one agent), `pipeline` (members run in order), `hub` (a lead delegates to members), `pool`
    (a dispatcher routes work to one member), `council` (3-9 members answer, a decision rule combines them).
    Leave `parent_id` empty for the root unit; nested units name their parent.

    Arguments:
        unit_id: Lowercase kebab-case id; matching an existing unit updates it and keeps its members.
        name: Display name.
        model: The governance model.
        parent_id: The parent unit's id, or none for the root unit.
        routing: Pool routing rule.
        decision: Council decision rule.
        owners: Approver emails for actions inside this unit.
        max_autonomy: Ceiling on the autonomy of agents inside this unit.
        monthly_usd: Monthly budget cap of this unit.
        approval_required: Action classes this unit governs in addition to the org's.

    Returns:
        message: Confirmation and whether the org structure is complete.
    """
    existing = _unit(unit_id)
    fields: dict[str, Any] = {
        'id': unit_id,
        'name': name,
        'model': model,
        'parent_id': parent_id,
        'routing': routing,
        'decision': decision,
        'owners': owners or [],
        'max_autonomy': max_autonomy,
        'monthly_usd': monthly_usd,
        'approval_required': approval_required or [],
    }
    if existing is not None:
        fields |= {'lead': existing.lead, 'members': existing.members, 'step_reviews': existing.step_reviews}
        fields |= {'step_instructions': existing.step_instructions}
    try:
        draft = UnitDraft.model_validate(fields)
    except ValidationError as error:
        return f'Unit not saved: {_first_error(error)}'
    state = get_state()
    state.units = [unit for unit in state.units if unit.id != unit_id] + [draft]
    return f"{'Updated' if existing else 'Added'} unit '{unit_id}'. {_sync_structure()}"


def set_pipeline_step(
    *,
    unit_id: str,
    member_id: str,
    instruction: str = '',
    review: Literal['none', 'lead', 'human'] = 'none',
) -> str:
    """Set the instruction and review gate of one member's step in a pipeline unit.

    Arguments:
        unit_id: The pipeline unit.
        member_id: The agent or unit that runs the step.
        instruction: What the step does with the previous step's output.
        review: `human` pauses for a person's approval, `lead` asks the nearest lead, `none` continues.

    Returns:
        message: Confirmation and whether the org structure is complete.
    """
    unit = _unit(unit_id)
    if unit is None or unit.model != 'pipeline':
        return f"No pipeline unit '{unit_id}'."
    unit.step_instructions[member_id] = instruction
    unit.step_reviews[member_id] = review
    return f"Set step '{member_id}' of '{unit_id}'. {_sync_structure()}"


def remove_unit(unit_id: str) -> str:
    """Remove an empty unit; move or remove its members and nested units first.

    Arguments:
        unit_id: The unit to remove.

    Returns:
        message: Confirmation, or why the unit cannot be removed.
    """
    state = get_state()
    unit = _unit(unit_id)
    if unit is None:
        return f"No unit named '{unit_id}'."
    nested = [u.id for u in state.units if u.parent_id == unit_id]
    if unit.members or unit.lead or nested:
        held = [*unit.members, *([unit.lead] if unit.lead else []), *nested]
        return f"Unit '{unit_id}' still holds {held}; move them first."
    state.units = [u for u in state.units if u.id != unit_id]
    return f"Removed unit '{unit_id}'. {_sync_structure()}"


def add_or_update_agent(
    *,
    agent_id: str,
    name: str,
    role: str,
    unit_id: str,
    as_lead: bool = False,
    tone: Literal['direct', 'warm', 'formal', 'playful'] = 'direct',
    verbosity: Literal['terse', 'balanced', 'thorough'] = 'balanced',
    instructions: str = '',
    in_scope: list[str] | None = None,
    out_of_scope: dict[str, str] | None = None,
    model: Literal['opus', 'sonnet', 'haiku'] = 'sonnet',
    autonomy: Literal['read_only', 'propose', 'act', 'autonomous'] = 'propose',
    builtin_tools: list[str] | None = None,
    tools: list[str] | None = None,
    mcp_servers: list[dict[str, Any]] | None = None,
    skills: list[str] | None = None,
    workspace: Literal['ephemeral', 'persistent', 'shared'] = 'ephemeral',
    memory: Literal['none', 'session', 'user'] = 'session',
    max_turns: int = 30,
    max_run_usd: float | None = None,
    timeout_s: int = 600,
    output_format: Literal['text', 'json'] = 'text',
    output_schema: dict[str, Any] | None = None,
    knowledge_type: str | None = None,
    replicas: int = 1,
    tags: list[str] | None = None,
) -> str:
    """Add or update an agent and place it in a unit, as a member or as the unit's lead.

    Arguments:
        agent_id: Lowercase kebab-case id; matching an existing agent updates it.
        name: Display name.
        role: One sentence on what the agent is responsible for.
        unit_id: The unit the agent belongs to; create it first with `add_or_update_unit`.
        as_lead: Make the agent the unit's lead instead of a member (hubs need one; pools and judge councils may).
        tone: `direct`, `warm`, `formal` or `playful`.
        verbosity: `terse`, `balanced` or `thorough`.
        instructions: How the agent works, in prose.
        in_scope: Topics the agent owns.
        out_of_scope: Topics the agent declines, mapped to the agent or unit it refers them to.
        model: `opus` for leads and hard reasoning, `sonnet` by default, `haiku` for fast triage.
        autonomy: `read_only`, `propose` (writes need approval), `act`, or `autonomous`.
        builtin_tools: Harness tools from read, write, edit, glob, grep, bash, web_search, web_fetch, todo; defaults
            follow the autonomy.
        tools: Names of custom tools registered with `emit_custom_tool`.
        mcp_servers: MCP servers, each with name, transport (stdio/http/sse), command/args or url, env (env var
            names), and optional allowed_tools, read_tools, outbound_tools.
        skills: Names of skills registered with `emit_custom_skill`.
        workspace: `ephemeral`, `persistent` or `shared` (with its unit).
        memory: `none`, `session` or `user`.
        max_turns: Turn cap per run.
        max_run_usd: USD cap per run; the org's per-run budget when unset.
        timeout_s: Wall-clock cap per run in seconds.
        output_format: `text` or `json`.
        output_schema: JSON schema of the output when `output_format` is `json`.
        knowledge_type: Knowledge type the agent's successful outputs are filed under.
        replicas: Parallel instances of this agent.
        tags: Skill tags pools route work by.

    Returns:
        message: Confirmation and whether the org structure is complete, or why the agent was not saved.
    """
    state = get_state()
    unit = _unit(unit_id)
    if unit is None:
        return f"No unit named '{unit_id}'. Create it first with add_or_update_unit."
    unknown_tools = [name for name in tools or [] if name not in state.functions]
    if unknown_tools:
        return f'Unknown custom tools {unknown_tools}; register them with emit_custom_tool first.'
    fields: dict[str, Any] = {
        'id': agent_id,
        'name': name,
        'role': role,
        'persona': {
            'tone': tone,
            'verbosity': verbosity,
            'instructions': instructions,
            'in_scope': in_scope or [],
            'out_of_scope': [{'topic': topic, 'refer_to': target} for topic, target in (out_of_scope or {}).items()],
        },
        'model': model,
        'autonomy': autonomy,
        'builtin_tools': builtin_tools,
        'tools': [state.functions[name] for name in tools or []],
        'mcp_servers': mcp_servers or [],
        'skills': skills or [],
        'workspace': workspace,
        'memory': memory,
        'limits': {'max_turns': max_turns, 'max_run_usd': max_run_usd, 'timeout_s': timeout_s},
        'output': {'format': output_format, 'json_schema': output_schema, 'knowledge_type': knowledge_type},
        'replicas': replicas,
        'tags': tags or [],
    }
    try:
        agent = Agent.model_validate(fields)
    except ValidationError as error:
        return f'Agent not saved: {_first_error(error)}'
    existed = any(a.id == agent_id for a in state.agents)
    state.agents = [a for a in state.agents if a.id != agent_id] + [agent]
    _detach(agent_id)
    if as_lead:
        unit.lead = agent_id
    else:
        unit.members.append(agent_id)
    return f"{'Updated' if existed else 'Added'} agent '{agent_id}' in '{unit_id}'. {_sync_structure()}"


def remove_agent(agent_id: str) -> str:
    """Remove the agent with the given id from the org and its unit.

    Arguments:
        agent_id: The agent to remove.

    Returns:
        message: Confirmation and whether the org structure is complete, or a not-found message.
    """
    state = get_state()
    if not any(agent.id == agent_id for agent in state.agents):
        return f"No agent named '{agent_id}'."
    state.agents = [agent for agent in state.agents if agent.id != agent_id]
    _detach(agent_id)
    return f"Removed agent '{agent_id}'. {_sync_structure()}"


def add_or_update_trigger(
    *,
    trigger_id: str,
    kind: Literal['schedule', 'event', 'webhook', 'queue'],
    target: str,
    prompt: str,
    cron: str | None = None,
    timezone: str = 'UTC',
    overlap: Literal['skip', 'queue', 'allow'] = 'skip',
    catch_up: Literal['skip', 'run_once'] = 'skip',
    event: str | None = None,
    filter: dict[str, Any] | None = None,  # noqa: A002 - the spec field is named filter
    secret_env: str | None = None,
    queue: str | None = None,
    url_env: str | None = None,
    enabled: bool = True,
) -> str:
    """Add or update a trigger that starts runs of an agent or unit without a person asking.

    Arguments:
        trigger_id: Lowercase kebab-case id.
        kind: `schedule` (cron), `event` (org event), `webhook` (signed HTTP call) or `queue` (external AMQP queue).
        target: The agent or unit the trigger runs.
        prompt: The run's input; may use {now}, {trigger_id}, {event}, {body}, {message} and parameter names.
        cron: 5-field cron expression, for schedules.
        timezone: IANA timezone of the cron, for schedules.
        overlap: What a schedule does while its previous run is active: skip, queue or allow.
        catch_up: What a schedule does with fires missed during downtime: skip or run_once.
        event: Event name, built in or `custom.*`, for event triggers.
        filter: Payload fields that must match, for event and queue triggers.
        secret_env: Env var holding the HMAC secret, for webhooks; declare it with add_or_update_env_var.
        queue: Queue name, for queue triggers.
        url_env: Env var of a different broker, for queue triggers.
        enabled: Whether the trigger fires.

    Returns:
        message: Confirmation, or the validation error with the spec unchanged.
    """
    specific: dict[str, dict[str, Any]] = {
        'schedule': {'cron': cron, 'timezone': timezone, 'overlap': overlap, 'catch_up': catch_up},
        'event': {'event': event, 'filter': filter or {}},
        'webhook': {'secret_env': secret_env},
        'queue': {'queue': queue, 'filter': filter or {}, 'url_env': url_env},
    }
    trigger = {'kind': kind, 'id': trigger_id, 'target': target, 'prompt': prompt, 'enabled': enabled, **specific[kind]}
    others = [t.model_dump() for t in get_state().spec.operations.triggers if t.id != trigger_id]
    error = _set_operations(triggers=[*others, trigger])
    if error:
        return f"Trigger '{trigger_id}' not saved: {error}"
    return f"Saved {kind} trigger '{trigger_id}' on '{target}'."


def remove_trigger(trigger_id: str) -> str:
    """Remove the trigger with the given id.

    Arguments:
        trigger_id: The trigger to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    triggers = get_state().spec.operations.triggers
    if not any(t.id == trigger_id for t in triggers):
        return f"No trigger named '{trigger_id}'."
    _set_operations(triggers=[t.model_dump() for t in triggers if t.id != trigger_id])
    return f"Removed trigger '{trigger_id}'."


def _set_operations(**sections: Any) -> str | None:  # noqa: ANN401
    """Replace operations sections when the whole spec still validates; return the error otherwise."""
    current = get_state().spec.operations.model_dump()
    try:
        operations = Operations.model_validate({**current, **sections})
    except ValidationError as error:
        return _first_error(error)
    return _rebuild_spec(operations=operations)


def _section_update(section: str, values: dict[str, Any]) -> str | None:
    """Update fields of one operations section when the spec still validates."""
    current = getattr(get_state().spec.operations, section).model_dump()
    return _set_operations(**{section: {**current, **{k: v for k, v in values.items() if v is not None}}})


def set_budget(
    *,
    monthly_usd: float,
    per_run_usd: float | None = None,
    alert_at: float | None = None,
    on_exhausted: Literal['pause', 'notify_only'] | None = None,
) -> str:
    """Set the org's USD budget.

    Arguments:
        monthly_usd: Monthly spending cap.
        per_run_usd: Default cap of a single run.
        alert_at: Fraction of the monthly cap that triggers an alert, such as 0.8.
        on_exhausted: `pause` the org or `notify_only` when the cap is reached.

    Returns:
        message: Confirmation, or the validation error.
    """
    values = {
        'monthly_usd': monthly_usd,
        'per_run_usd': per_run_usd,
        'alert_at': alert_at,
        'on_exhausted': on_exhausted,
    }
    error = _section_update('budget', values)
    return f'Budget not saved: {error}' if error else f'Budget set to {monthly_usd} USD per month.'


def set_lifecycle(
    *,
    initial: Literal['draft', 'trial', 'active'] | None = None,
    trial_max_runs: int | None = None,
    max_failure_rate: float | None = None,
    failure_window: int | None = None,
) -> str:
    """Set the org's initial lifecycle state, trial cap and failure-rate circuit breaker.

    Arguments:
        initial: The state a new deployment starts in; `trial` holds every write for approval.
        trial_max_runs: Runs allowed during the trial.
        max_failure_rate: Failure fraction that auto-pauses the org.
        failure_window: Number of recent runs the failure rate is measured over.

    Returns:
        message: Confirmation, or the validation error.
    """
    values = {
        'initial': initial,
        'trial_max_runs': trial_max_runs,
        'max_failure_rate': max_failure_rate,
        'failure_window': failure_window,
    }
    error = _section_update('lifecycle', values)
    return f'Lifecycle not saved: {error}' if error else 'Lifecycle settings saved.'


def set_approvers(emails: list[str]) -> str:
    """Set the people who approve governed actions when no unit owner is closer.

    Arguments:
        emails: Approver emails.

    Returns:
        message: Confirmation, or the validation error.
    """
    invalid = [email for email in emails if not _is_valid_email(email)]
    if invalid:
        return f'These do not look like emails: {invalid}.'
    error = _section_update('governance', {'approvers': emails})
    return f'Approvers not saved: {error}' if error else f'Approvers set: {", ".join(emails)}.'


def set_governance(
    *,
    approval_required: list[str] | None = None,
    approval_timeout_h: float | None = None,
    on_timeout: Literal['reject', 'approve'] | None = None,
    spend_threshold_usd: float | None = None,
) -> str:
    """Set which action classes need human approval and what happens when nobody decides.

    Arguments:
        approval_required: Classes from external_write, outbound_message, code_execution, knowledge_publish, spend.
        approval_timeout_h: Hours before an undecided approval times out.
        on_timeout: `reject` or `approve` on timeout.
        spend_threshold_usd: Projected run cost above which `spend` applies.

    Returns:
        message: Confirmation, or the validation error.
    """
    values = {
        'approval_required': approval_required,
        'approval_timeout_h': approval_timeout_h,
        'on_timeout': on_timeout,
        'spend_threshold_usd': spend_threshold_usd,
    }
    error = _section_update('governance', values)
    return f'Governance not saved: {error}' if error else 'Governance saved.'


def set_notifications(
    *,
    channels: list[str],
    email_to: list[str] | None = None,
    webhook_url_env: str | None = None,
    amqp_exchange: str | None = None,
) -> str:
    """Set where notifications go; the dashboard always receives them.

    Arguments:
        channels: Channels from dashboard, email, webhook, amqp.
        email_to: Recipients for the email channel.
        webhook_url_env: Env var holding the webhook URL; declare it with add_or_update_env_var.
        amqp_exchange: Exchange for the amqp channel.

    Returns:
        message: Confirmation, or the validation error.
    """
    values = {
        'channels': channels,
        'email_to': email_to,
        'webhook_url_env': webhook_url_env,
        'amqp_exchange': amqp_exchange,
    }
    error = _section_update('notifications', values)
    return f'Notifications not saved: {error}' if error else f'Notifications go to {", ".join(channels)}.'


def set_run_policy(
    *,
    max_concurrent: int | None = None,
    retries: int | None = None,
    on_failure: Literal['notify', 'escalate', 'handoff'] | None = None,
    fallback_agent: str | None = None,
    retention_days: int | None = None,
) -> str:
    """Set concurrency, retries and what happens to runs that keep failing.

    Arguments:
        max_concurrent: Runs one worker executes at once.
        retries: Automatic retries of a failed run.
        on_failure: `notify`, `escalate` to the inbox, or `handoff` to the fallback agent.
        fallback_agent: The agent that takes over failed runs under `handoff`.
        retention_days: Days run history is kept.

    Returns:
        message: Confirmation, or the validation error.
    """
    values = {
        'max_concurrent': max_concurrent,
        'retries': retries,
        'on_failure': on_failure,
        'fallback_agent': fallback_agent,
        'retention_days': retention_days,
    }
    error = _section_update('runs', values)
    return f'Run policy not saved: {error}' if error else 'Run policy saved.'


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


DISCOVERY_MIN_LEN = 100
STAGE1_MIN_PRINCIPLE_BODY_LEN = 200
STAGE2_DESCRIPTION_MIN_LEN = 200


def record_discovery_summary(
    *,
    what_the_group_does: str,
    who_serves: str,
    concrete_tasks_owned: str,
    typical_flow: str,
    business_context: str,
    current_pain_or_alternative: str,
    user_confirmed: bool,
) -> str:
    """Record your understanding of the business before drafting principles or the description.

    Call this during Stage 1 once you have probed enough that you can describe the
    business specifically. "Pharma company designing longevity drugs" is NOT enough -
    you need to know what KIND of drugs, what stage of development, what the agents
    will actually do, who the customers are. Each text field must be 100+ characters
    and reference real specifics from what the user told you, not generic placeholders.

    `add_or_update_principle_section` and `set_org_identity(description=...)` are blocked in
    Stage 1 until this tool succeeds.

    Arguments:
        what_the_group_does: 100+ chars. The concrete activity. "Designs small-molecule
            drugs that target senescent cell pathways; runs pre-clinical screening
            in-house and partners with CROs for trials." NOT "designs longevity drugs".
        who_serves: 100+ chars. Specific audience with demographics or role. "Patients
            with age-related diseases, prescribed via specialist physicians at academic
            medical centres; secondary audience is biotech investors evaluating pipeline."
            NOT "people who want to live longer".
        concrete_tasks_owned: 100+ chars. List 3-5 specific tasks/processes the group
            owns end-to-end, separated by semicolons. "Literature review for novel
            targets; in-vitro compound screening; IND-enabling tox studies; clinical
            trial protocol design; FDA submission preparation." NOT "drug development".
        typical_flow: 100+ chars. A specific end-to-end walkthrough. "Scientist
            proposes a target -> agents survey the literature and competitor pipelines ->
            shortlist compounds -> design assays -> external lab runs them -> agents
            summarise results into a go/no-go report." NOT "we develop drugs".
        business_context: 100+ chars. Market segment + differentiator, or the
            organisational context for an internal team. "Pre-clinical longevity biotech,
            seed-stage, competing with Altos and Retro Bio on aging biology but
            differentiating on small-molecule modality vs cellular reprogramming."
        current_pain_or_alternative: 100+ chars. What's happening today (or would
            happen without this group), and the gap. "Today a single PhD spends 2-3
            weeks doing the target review manually; we want agents to compress that to
            48 hours so we can survey 10x more targets per quarter."
        user_confirmed: Set True ONLY if you have asked the user some variant of "does
            this capture what you have in mind?" in this conversation AND received an
            affirmative reply. Otherwise set False; the tool refuses.

    Returns:
        message: `Recorded` confirmation, or a rejection naming the specific field(s)
            that are too short / not yet user-confirmed.
    """
    blockers: list[str] = []
    if not user_confirmed:
        blockers.append(
            "user_confirmed is False - ask the user 'does this capture what you have in "
            "mind?' first, get an affirmative reply, then call this tool with user_confirmed=True.",
        )
    fields = {
        'what_the_group_does': what_the_group_does,
        'who_serves': who_serves,
        'concrete_tasks_owned': concrete_tasks_owned,
        'typical_flow': typical_flow,
        'business_context': business_context,
        'current_pain_or_alternative': current_pain_or_alternative,
    }
    for name, value in fields.items():
        n = len(value.strip())
        if n < DISCOVERY_MIN_LEN:
            blockers.append(
                f"{name!r} is only {n} chars (need at least {DISCOVERY_MIN_LEN}) - "
                f"keep probing the user, then retry with specifics from their answers.",
            )
    if blockers:
        return 'REJECTED - discovery is not specific enough yet:\n  - ' + '\n  - '.join(blockers)

    state = get_state()
    state.discovery = Discovery(
        what_the_group_does=what_the_group_does.strip(),
        who_serves=who_serves.strip(),
        concrete_tasks_owned=concrete_tasks_owned.strip(),
        typical_flow=typical_flow.strip(),
        business_context=business_context.strip(),
        current_pain_or_alternative=current_pain_or_alternative.strip(),
    )
    return (
        'Recorded. You may now draft principle sections via add_or_update_principle_section '
        'and set a substantive description via set_org_identity(description=...).'
    )


def _stage1_discovery_gate_message() -> str:
    """Error returned by Stage-1 tools that require `record_discovery_summary` first."""
    return (
        "Blocked: in Stage 1 (Discover), you must call `record_discovery_summary` BEFORE "
        "drafting principles. Ask the user follow-up questions until you can describe the "
        "business specifically across all six fields, get their confirmation, then call "
        "`record_discovery_summary(...)`."
    )


def _check_description_length(description: str | None) -> str | None:
    """Quality gate: when Configure writes a description, demand 200+ chars.

    The cross-stage leak gate that used to live here is gone: `set_org_identity` is only
    in the Configure agent's tool slice, so the Discover agent literally can't call it.
    All that remains is the description-length quality check.
    """
    if description is None:
        return None
    desc = description.strip()
    if len(desc) < STAGE2_DESCRIPTION_MIN_LEN:
        return (
            f"Description too short ({len(desc)} chars). Write at least "
            f"{STAGE2_DESCRIPTION_MIN_LEN} characters - 2-4 sentences covering "
            "mission, audience, and what makes this group distinctive. You have the "
            "discovery summary from Stage 1; draft from it and ask the user to confirm."
        )
    return None


def add_or_update_principle_section(*, section_id: str, title: str, body: str) -> str:
    """Add or update one section of the org's principles.

    Stage 1 gate: blocked until `record_discovery_summary` is called. In later stages
    (refine, etc.) this gate is off - the assumption is that discovery happened.

    Arguments:
        section_id: Stable identifier; matching an existing section triggers an update.
        title: Section heading.
        body: Markdown body, may reference parameters as `{param_name}`.

    Returns:
        message: `Added` or `Updated` confirmation, or the Stage-1 gate message.
    """
    state = get_state()
    if state.stage == 'discover' and state.discovery is None:
        return _stage1_discovery_gate_message()
    if state.stage == 'discover' and len(body.strip()) < STAGE1_MIN_PRINCIPLE_BODY_LEN:
        return (
            f"Stage-1 principle body too short ({len(body.strip())} chars). Write at "
            f"least {STAGE1_MIN_PRINCIPLE_BODY_LEN} characters - a real paragraph that "
            "explains the principle in context (what it means in day-to-day decisions, "
            "what trade-offs it implies). One-line slogans like 'Quality matters' are "
            "not principles - they're labels. If the user said 'you decide', go back and "
            "ask them 2-3 specific multiple-choice questions to ground the principle in "
            "their business, then write the paragraph."
        )
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


def emit_custom_tool(*, name: str, source: str, test_cases: list[dict]) -> str:
    """Validate and register a user-defined async tool function.

    The `source` must define a top-level `async def <name>(...)` returning a string. The
    sandbox validates the body in four passes: parse, async-def lookup, placeholder-pattern
    scan (rejects empty bodies, `raise NotImplementedError`, and `TODO`/`placeholder`/etc.
    string literals), and a subprocess that imports the source and runs every test case
    against the function. The tool is rejected if any pass fails.

    `test_cases` is required and must be non-empty. Each case is one of:
        {'input': {'message': 'hello'}, 'expected_contains': 'hello'}
        {'input': {}, 'expected_equals': 'pong'}
        {'input': {'amount': 100}, 'expected_raises': 'STRIPE_SECRET_KEY'}
    Each case may also include `env={'KEY': 'value'}` (set for the case) or
    `drop_env=['KEY']` (removed for the case). Tools that need credentials should write the
    real body that reads `os.environ['VAR']` and use `expected_raises='VAR'` together with
    `drop_env=['VAR']` to prove the env-var read happens. Then declare the credential via
    `add_or_update_env_var` and the setup task via `add_or_update_setup_step`.

    Arguments:
        name: The function name that must appear in `source` as `async def <name>(...)`.
        source: Complete Python source code defining the function (and any imports it needs).
        test_cases: Non-empty list of test cases the sandbox runs against the imported function.

    Returns:
        message: `Registered` or `Updated` confirmation, or a validation-error description.
    """
    try:
        validate_tool_source(name, source, test_cases=test_cases)
    except ToolValidationError as exc:
        return f"Validation failed for '{name}': {exc}"
    state = get_state()
    new_tools, existed = _upsert(list(state.custom_tools), 'name', name, CustomTool(name=name, source=source))
    state.custom_tools = new_tools
    function = compile_tool(name, source)
    state.functions[name] = function
    for agent in state.agents:
        agent.__dict__['tools'] = [function if fn.__name__ == name else fn for fn in agent.tools]
    _sync_structure()
    return f"{'Updated' if existed else 'Registered'} custom tool '{name}'."


def remove_custom_tool(name: str) -> str:
    """Remove the custom tool with the given `name`.

    Arguments:
        name: Name of the tool to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    state = get_state()
    users = [agent.id for agent in state.agents if any(fn.__name__ == name for fn in agent.tools)]
    if users:
        return f"Custom tool '{name}' is used by {users}; update those agents first."
    new_tools, removed = _remove(list(state.custom_tools), 'name', name)
    if not removed:
        return f"No custom tool named '{name}'."
    state.custom_tools = new_tools
    state.functions.pop(name, None)
    return f"Removed custom tool '{name}'."


def emit_custom_skill(*, name: str, skill_md: str) -> str:
    """Validate and register a user-defined skill (SKILL.md folder).

    The `skill_md` is the full markdown body of a SKILL.md file. Validation is structural:
    the name must be lowercase-with-hyphens, and the markdown must start with an H1 heading
    plus at least one line of content. On success the skill is stored in state and will be
    materialised at `finalize_spec` time as a `skills/<name>/SKILL.md` folder next to the
    rendered `spec.py`. Agents reference it via `skills=['custom:<name>']`.

    Arguments:
        name: Folder name for the skill, lowercase-with-hyphens (e.g. `'negotiation-playbook'`).
        skill_md: Full markdown body of the SKILL.md file.

    Returns:
        message: `Registered` or `Updated` confirmation, or a validation-error description.
    """
    try:
        validate_skill_source(name, skill_md)
    except SkillValidationError as exc:
        return f"Validation failed for '{name}': {exc}"
    state = get_state()
    new_skills, existed = _upsert(list(state.custom_skills), 'name', name, CustomSkill(name=name, skill_md=skill_md))
    state.custom_skills = new_skills
    return f"{'Updated' if existed else 'Registered'} custom skill '{name}'."


def remove_custom_skill(name: str) -> str:
    """Remove the custom skill with the given `name`.

    Arguments:
        name: Name of the skill to remove.

    Returns:
        message: Confirmation, or a not-found message.
    """
    state = get_state()
    new_skills, removed = _remove(list(state.custom_skills), 'name', name)
    if not removed:
        return f"No custom skill named '{name}'."
    state.custom_skills = new_skills
    return f"Removed custom skill '{name}'."


async def sandbox_agent(*, agent_id: str, test_prompts: list[str]) -> str:
    """Run a committed agent on real prompts in preview mode and report outputs, tool calls and cost.

    The agent runs on the Claude agent harness with its real model, tools and MCP servers. Preview mode denies
    consequential actions, so write tools report what they would do instead of doing it.

    Arguments:
        agent_id: The id of an agent added with `add_or_update_agent`.
        test_prompts: One or more prompts to run in order: a happy path, an edge case and an error case.

    Returns:
        report: A markdown report with each prompt's status, output, tool calls and cost.
    """
    from ._agent_sandbox import sandbox_run  # noqa: PLC0415 - the runtime is heavy and only the Build stage needs it

    state = get_state()
    if state.structure_error is not None:
        return f'Finish the org structure first: {state.structure_error}'
    if not any(agent.id == agent_id for agent in state.spec.ai.agents):
        return f"No agent named '{agent_id}'. Add it first via add_or_update_agent."
    if not test_prompts:
        return 'sandbox_agent needs at least one test prompt.'
    return await sandbox_run(state.spec, agent_id, test_prompts, state.custom_skills)


def get_current_spec() -> str:
    """Return the working spec as the spec.py source it would be written as.

    Returns:
        source: The spec.py source of the current spec, custom tools included.
    """
    state = get_state()
    return render_spec(state.spec, custom_tools=state.custom_tools, custom_skills=state.custom_skills)


def advance_to_next_stage() -> str:
    """Move the interview from the current stage to the next one.

    Call this tool *only* when the user has explicitly confirmed they want to advance
    (e.g. "yes let's move on", "ready", "next stage"). Do NOT call it pre-emptively.
    The tool checks the stage's blockers; if any are unmet the call is rejected and the
    blockers are returned so you can tell the user what's missing.

    Returns:
        message: A short string describing the outcome - either "Advanced to Stage N -
            Label." (success) or "Cannot advance: ..." with the blocker list.
    """
    state = get_state()
    prev_stage = state.stage
    ok, new_stage, blockers = advance(state)
    if not ok:
        if blockers and blockers[0] == 'Already on the final stage.':
            return 'Already on the final stage; nothing to advance to.'
        bullets = '\n'.join(f'- {b}' for b in blockers)
        return f"Cannot advance from {STAGE_LABELS[prev_stage]} yet:\n{bullets}"
    prev_idx = STAGES.index(prev_stage) + 1
    new_idx = STAGES.index(new_stage) + 1
    return (
        f'Advanced from Stage {prev_idx} ({STAGE_LABELS[prev_stage]}) '
        f'to Stage {new_idx} ({STAGE_LABELS[new_stage]}).'
    )


def finalize_spec(output_path: str | Path) -> str:
    """Render the working spec to a `spec.py` file at `output_path`.

    Any custom skills registered via `emit_custom_skill` are materialised as
    `skills/<name>/SKILL.md` folders next to the rendered file.

    Arguments:
        output_path: Destination file path. Parent directories are created if missing.

    Returns:
        message: Absolute path of the file written.
    """
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    state = get_state()
    write_spec(state.spec, target, custom_tools=state.custom_tools, custom_skills=state.custom_skills)
    for skill in state.custom_skills:
        skill_dir = target.parent / 'skills' / skill.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / 'SKILL.md').write_text(skill.skill_md)
    return f'Wrote {target}.'
