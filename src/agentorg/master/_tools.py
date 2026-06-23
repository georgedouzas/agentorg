"""Patch tools the master agent calls to update the working spec."""

import re
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

from ._models import AgentSpec, CustomSkill, CustomTool, StepSpec, TeamSpec, WorkflowSpec
from ._sandbox import SkillValidationError, ToolValidationError, validate_skill_source, validate_tool_source
from ._seed import PLACEHOLDER_VALUES
from ._stages import STAGE_LABELS, STAGES, advance
from ._state import Discovery, get_state
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


_ORG_STRING_FIELDS: tuple[str, ...] = (
    'name',
    'slug',
    'package_name',
    'description',
    'repository',
    'admin_name',
    'admin_email',
)


def _org_placeholders(spec: Spec) -> list[tuple[str, str]]:
    """Return placeholder entries for the seed-valued fields on `spec.org`."""
    return [(f'org.{f}', getattr(spec.org, f)) for f in _ORG_STRING_FIELDS if _is_placeholder(getattr(spec.org, f))]


def _ai_placeholders(spec: Spec) -> list[tuple[str, str]]:
    """Return placeholder entries for empty agent/team/workflow collections + toolless agents."""
    out: list[tuple[str, str]] = []
    if not spec.ai.agents:
        out.append(('ai.agents', '(empty)'))
    for agent in spec.ai.agents:
        if isinstance(agent, AgentSpec) and not agent.tools and not agent.skills:
            out.append((f'ai.agents[{agent.agent_id}].tools_or_skills', '(empty)'))
    if not spec.ai.teams:
        out.append(('ai.teams', '(empty)'))
    if not spec.ai.workflows:
        out.append(('ai.workflows', '(empty)'))
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


_EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$')
_GIT_HTTPS_RE = re.compile(r'^https?://[A-Za-z0-9.\-]+(?::\d+)?(?:/[^/\s]+)+/?$')
_GIT_SSH_RE = re.compile(r'^git@[A-Za-z0-9.\-]+:[^/\s][^/\s]*/[^/\s]+(?:\.git)?$')
_REPO_PLACEHOLDER_SUFFIX = '/TODO'


def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value))


def _is_valid_repository(value: str) -> bool:
    """Validate a repository URL.

    Recognises the seed placeholder and `https://example.com/TODO`.
    """
    if value in PLACEHOLDER_VALUES or value.endswith(_REPO_PLACEHOLDER_SUFFIX):
        return True
    return bool(_GIT_HTTPS_RE.match(value) or _GIT_SSH_RE.match(value))


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
    budget: Literal['low', 'medium', 'high'] | None = None,
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
        budget: Guidance tier for fleet size and tool depth (`low` / `medium` / `high`).

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
        'budget': budget,
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


def add_or_update_agent(
    *,
    agent_id: str,
    name: str,
    role: str,
    in_scope: list[str],
    workflow: list[str],
    tools: list[str] | None = None,
    skills: list[str] | None = None,
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
        skills: Names of skill-catalog refs (keys of `DEFAULT_SKILLS_REFS`) the agent uses.
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
    # Tools use BARE names (`run_sqlite_query`), not the `custom:` prefix (that's for
    # skills only). Normalise at the entry point so the LLM can't break the rendered
    # spec.py with `tools=['custom:foo']` (which would emit `import custom:foo` and
    # syntax-error on reload).
    normalised_tools = [t.removeprefix('custom:') for t in (tools or [])]
    spec = AgentSpec(
        agent_id=agent_id,
        name=name,
        role=role,
        model=model,
        tools=normalised_tools,
        skills=skills or [],
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
    tools: list[str] | None = None,
    skills: list[str] | None = None,
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
        tools: Names of built-in or custom tools available at the team level (in addition to
            anything its members can call).
        skills: Skill-catalog refs the team's orchestrator can use. Plain catalog refs
            (`'superpowers'`) load the whole catalog; granular refs (`'superpowers/negotiation'`)
            load a single subfolder.
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
    normalised_tools = [t.removeprefix('custom:') for t in (tools or [])]
    spec = TeamSpec(
        team_id=team_id,
        name=name,
        role=role,
        model=model,
        member_ids=member_ids,
        mode=mode,
        tools=normalised_tools,
        skills=skills or [],
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


_DISCOVERY_MIN_LEN = 100
_STAGE1_MIN_PRINCIPLE_BODY_LEN = 200
_STAGE2_DESCRIPTION_MIN_LEN = 200


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
    """Record your understanding of the business before drafting principles, description, or budget.

    Call this during Stage 1 once you have probed enough that you can describe the
    business specifically. "Pharma company designing longevity drugs" is NOT enough -
    you need to know what KIND of drugs, what stage of development, what the agents
    will actually do, who the customers are. Each text field must be 100+ characters
    and reference real specifics from what the user told you, not generic placeholders.

    `add_or_update_principle_section`, `set_org_identity(budget=...)`, and
    `set_org_identity(description=...)` are blocked in Stage 1 until this tool succeeds.

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
        if n < _DISCOVERY_MIN_LEN:
            blockers.append(
                f"{name!r} is only {n} chars (need at least {_DISCOVERY_MIN_LEN}) - "
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
        'Recorded. You may now draft principle sections via add_or_update_principle_section, '
        'set a substantive description via set_org_identity(description=...), and pick a '
        'budget via set_org_identity(budget=...).'
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
    if len(desc) < _STAGE2_DESCRIPTION_MIN_LEN:
        return (
            f"Description too short ({len(desc)} chars). Write at least "
            f"{_STAGE2_DESCRIPTION_MIN_LEN} characters - 2-4 sentences covering "
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
    if state.stage == 'discover' and len(body.strip()) < _STAGE1_MIN_PRINCIPLE_BODY_LEN:
        return (
            f"Stage-1 principle body too short ({len(body.strip())} chars). Write at "
            f"least {_STAGE1_MIN_PRINCIPLE_BODY_LEN} characters - a real paragraph that "
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
    """Build the named agent for real and run the supplied prompts against it.

    The agent is instantiated via `make_agent` with tools and skills resolved from the
    current state (built-in catalog, custom tools, GitHub skill catalogs, and custom
    skills materialised on disk under a temp dir). The agent then runs each prompt via
    `arun`, calling the REAL model and executing REAL tools - any external side effects
    those tools have will happen.

    Use this in Stage 4 (Capability Audit) AFTER warning the user about side-effect risk
    and after they confirm the prompts to run.

    Arguments:
        agent_id: The `agent_id` of an existing `AgentSpec` in `spec.ai.agents`.
        test_prompts: One or more prompts to run sequentially.

    Returns:
        report: A markdown report covering each prompt's response, tool calls, and errors.
    """
    from ._agent_sandbox import sandbox_run  # noqa: PLC0415  (defer import; agno + skills loaders are heavy)

    state = get_state()
    agent_spec = next(
        (a for a in state.spec.ai.agents if isinstance(a, AgentSpec) and a.agent_id == agent_id),
        None,
    )
    if agent_spec is None:
        return f"No agent named '{agent_id}'. Add it first via add_or_update_agent."
    if not test_prompts:
        return 'sandbox_agent needs at least one test prompt.'
    return await sandbox_run(agent_spec, test_prompts, state.custom_tools, state.custom_skills)


def get_current_spec() -> Spec:
    """Return the working spec.

    Returns:
        spec: The current in-memory `Spec`.
    """
    return get_state().spec


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


def request_redeploy() -> str:
    """Write the working spec to `./spec.py` and instruct the operator to redeploy.

    Used by the production master agent when the user is ready to apply pending in-memory edits to the deployed org. The
    master mutates spec.py; the operator runs their own deploy pipeline (typically git push -> CI rebuild -> container
    redeploy).
    """
    target = Path('spec.py').resolve()
    state = get_state()
    write_spec(state.spec, target, custom_tools=state.custom_tools, custom_skills=state.custom_skills)
    for skill in state.custom_skills:
        skill_dir = target.parent / 'skills' / skill.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / 'SKILL.md').write_text(skill.skill_md)
    return (
        f'Wrote {target}.\n\n'
        'To apply on the running org, commit + push so your CI rebuilds and redeploys:\n'
        '  git add spec.py skills/\n'
        '  git commit -m "Update org spec"\n'
        '  git push\n\n'
        "Once the deploy completes the running org will reflect the changes."
    )
