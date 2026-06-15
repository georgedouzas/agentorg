"""Tests for the base module."""

import pytest
from agno.skills.loaders.local import LocalSkills
from agno.workflow import Step

from agentorg.core.agents.framework.agno import GitHubSkills, make_agent, make_team, make_workflow
from agentorg.core.agents.skills import DEFAULT_SKILLS_REFS

AGENT_ARGS = {
    'model': 'google:gemini-2.5-flash',
    'name': 'Code Reviewer',
    'agent_id': 'code-reviewer',
    'skills': [],
    'tools': [],
    'introduction': "Hi, I'm the code reviewer. Paste a diff or point me at a file and I'll flag issues.",
    'description': 'Reviews pull requests for correctness, security, and style before they merge to main.',
    'additional_context': (
        'Project is Python 3.12, uses Ruff for linting, and follows the conventions in the repo CLAUDE.md.'
    ),
    'role': 'Senior engineer responsible for reviewing code changes before they merge.',
    'principles': ['Prefer the smallest correct change.', 'Never approve code you have not read end-to-end.'],
    'when_to_act': [
        'A diff, pull request URL, or code snippet is provided: review it.',
        'A question about a previously reviewed change: answer from that context.',
        'No code in the message: ask for a diff or file path.',
    ],
    'in_scope': [
        'Reviewing diffs, pull requests, or pasted code snippets.',
        'Flagging bugs, security issues, and style violations.',
        'Suggesting concrete refactors with rationale.',
    ],
    'out_of_scope': [
        'Writing new features from scratch → **Software Engineer**',
        'Architectural or design decisions → **Tech Lead**',
        'Production incidents or on-call triage → **SRE**',
    ],
    'workflow': [
        'Read the diff or file in full before commenting.',
        'Group findings by severity: blocker, major, minor, nit.',
        'For each finding, cite file_path:line_number and propose a specific fix.',
        'End with a one-line verdict: approve, request changes, or comment.',
    ],
    'style': [
        'Be specific. "Line 42 leaks a file handle" beats "watch out for resource leaks".',
        'Lead with the problem, then the fix. No throat-clearing.',
        'Use file_path:line_number format so the reader can navigate.',
    ],
}
INSTRUCTIONS = """## Principles

*Org-wide rules every agent follows.*

- Prefer the smallest correct change.
- Never approve code you have not read end-to-end.

## When to act

*When this agent engages versus stays quiet.*

- A diff, pull request URL, or code snippet is provided: review it.
- A question about a previously reviewed change: answer from that context.
- No code in the message: ask for a diff or file path.

## In scope

*Topics this agent owns.*

- Reviewing diffs, pull requests, or pasted code snippets.
- Flagging bugs, security issues, and style violations.
- Suggesting concrete refactors with rationale.

## Out of scope

*Topics this agent declines, and the peer to refer to.*

- Writing new features from scratch → **Software Engineer**
- Architectural or design decisions → **Tech Lead**
- Production incidents or on-call triage → **SRE**

## Workflow

*Steps this agent follows for an in-scope request.*

- Read the diff or file in full before commenting.
- Group findings by severity: blocker, major, minor, nit.
- For each finding, cite file_path:line_number and propose a specific fix.
- End with a one-line verdict: approve, request changes, or comment.

## Style

*Tone and format rules for every response.*

- Be specific. "Line 42 leaks a file handle" beats "watch out for resource leaks".
- Lead with the problem, then the fix. No throat-clearing.
- Use file_path:line_number format so the reader can navigate."""
INSTRUCTIONS_TOOLS_SKILLS = """## Tools

*The only tools names you are allowed to mention in chat. Everything else is silent.*

- search_web
- fetch_url

## Skills

*The only skills names you are allowed to mention in chat. Everything else is silent.*

- greeter
- brainstorming"""


def test_instructions_composition():
    """Test the make instructions composition."""
    agent = make_agent(**AGENT_ARGS)
    assert agent.instructions == INSTRUCTIONS


@pytest.mark.network
def test_instructions_composition_with_tools_and_skills(cache_root):
    """Test the make agent instructions composition with tools and skills."""
    # Create skills
    skill_dir = cache_root / 'greeter'
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill = '---\nname: greeter\ndescription: Greets people warmly.\n---\n# Greeter\n'
    (skill_dir / 'SKILL.md').write_text(skill)
    local_skills = LocalSkills(str(cache_root))
    remote_skills = GitHubSkills(
        url=DEFAULT_SKILLS_REFS['superpowers']['url'],
        ref=DEFAULT_SKILLS_REFS['superpowers']['ref'],
        subpath=f'{DEFAULT_SKILLS_REFS["superpowers"]["subpath"]}/brainstorming',
    )

    # Create tools
    def search_web() -> None: ...
    def fetch_url() -> None: ...

    agent_extra_args = {'tools': [search_web, fetch_url], 'skills': [local_skills, remote_skills]}
    agent = make_agent(**{**AGENT_ARGS, **agent_extra_args})
    assert agent.instructions == f'{INSTRUCTIONS}\n\n{INSTRUCTIONS_TOOLS_SKILLS}'


def test_empty_when_to_act_falls_back_to_default():
    """An empty `when_to_act` substitutes the `WHEN_TO_ACT_DEFAULT` bullets into the instructions."""
    from agentorg.core.agents.framework.agno._base import WHEN_TO_ACT_DEFAULT  # noqa: PLC0415

    agent = make_agent(**{**AGENT_ARGS, 'when_to_act': []})
    instructions = agent.instructions or ''
    for line in WHEN_TO_ACT_DEFAULT:
        assert line in instructions


def test_empty_style_falls_back_to_default():
    """An empty `style` substitutes the `STYLE_DEFAULT` bullets into the instructions."""
    from agentorg.core.agents.framework.agno._base import STYLE_DEFAULT  # noqa: PLC0415

    agent = make_agent(**{**AGENT_ARGS, 'style': []})
    instructions = agent.instructions or ''
    for line in STYLE_DEFAULT:
        assert line in instructions


def test_kwargs_override_agno_defaults():
    """Extra `**kwargs` replace the corresponding entries in `AGENT_DEFAULTS`."""
    custom_history_runs = 99
    agent = make_agent(**{**AGENT_ARGS, 'telemetry': False, 'num_history_runs': custom_history_runs})
    assert agent.telemetry is False
    assert agent.num_history_runs == custom_history_runs


def test_agent_id_and_name_are_set():
    """`agent_id` and `name` reach the constructed agent verbatim."""
    agent = make_agent(**AGENT_ARGS)
    assert agent.id == 'code-reviewer'
    assert agent.name == 'Code Reviewer'


def test_skills_attribute_is_none_when_no_loaders_passed():
    """`skills=[]` leaves the agent with no Skills object — the `skills` attribute resolves to None."""
    agent = make_agent(**AGENT_ARGS)
    assert agent.skills is None


def _build_member_agent(agent_id: str, name: str) -> object:
    """Helper that builds a minimal agent suitable for use as a team member."""
    return make_agent(
        model='google:gemini-2.5-flash',
        name=name,
        agent_id=agent_id,
        role=f'{name} responsibilities.',
        tools=[],
        in_scope=['anything in scope'],
        workflow=['run the workflow'],
    )


_TEAM_BASE = {
    'model': 'google:gemini-2.5-flash',
    'name': 'Research Team',
    'team_id': 'research-team',
    'role': 'Coordinate research and analysis.',
    'workflow': ['Delegate to the researcher.', 'Then hand off to the analyst.'],
}


def test_make_team_sets_identity_and_membership():
    """`team_id`, `name`, `mode`, and `members` reach the constructed team verbatim."""
    members = [_build_member_agent('member-a', 'Member A'), _build_member_agent('member-b', 'Member B')]
    team = make_team(**_TEAM_BASE, members=members, mode='coordinate')
    assert team.id == 'research-team'
    assert team.name == 'Research Team'
    assert team.mode.value == 'coordinate'
    assert team.members == members


def test_make_team_defaults_mode_to_coordinate():
    """`mode` defaults to `coordinate` when omitted — the most common multi-agent shape."""
    team = make_team(**_TEAM_BASE, members=[_build_member_agent('m', 'M')])
    assert team.mode.value == 'coordinate'


def test_make_team_applies_team_defaults():
    """Entries in `TEAM_DEFAULTS` reach the team (in-memory db, markdown on, chat history readable)."""
    team = make_team(**_TEAM_BASE, members=[_build_member_agent('m', 'M')])
    assert team.db is not None
    assert team.markdown is True
    assert team.read_chat_history is True


def test_make_team_kwargs_override_team_defaults():
    """Extra `**kwargs` replace the corresponding entries in `TEAM_DEFAULTS`."""
    team = make_team(**_TEAM_BASE, members=[_build_member_agent('m', 'M')], markdown=False)
    assert team.markdown is False


def test_make_team_composes_instructions_from_persona_sections():
    """A team built with principles/in_scope/style gets those sections rendered into `instructions`."""
    team = make_team(
        **_TEAM_BASE,
        members=[_build_member_agent('m', 'M')],
        principles=['Coordinate without micromanaging.'],
        in_scope=['Multi-step research deliverables'],
        out_of_scope=['Single-shot lookups -> **Researcher**'],
        style=['Hand off cleanly; do not narrate routing decisions.'],
    )
    assert '## Principles' in team.instructions
    assert 'Coordinate without micromanaging.' in team.instructions
    assert '## In scope' in team.instructions
    assert 'Multi-step research deliverables' in team.instructions
    assert '## Style' in team.instructions


def test_make_team_lists_members_under_a_members_section():
    """The team's `instructions` carry a `Members` section listing each member by name."""
    members = [_build_member_agent('researcher', 'Researcher'), _build_member_agent('analyst', 'Analyst')]
    team = make_team(**_TEAM_BASE, members=members)
    assert '## Members' in team.instructions
    assert '- Researcher' in team.instructions
    assert '- Analyst' in team.instructions
    assert '## Tools' not in team.instructions  # teams render Members, not Tools


def test_make_team_installs_prompt_injection_guardrail():
    """Persona-aware teams get the same `PromptInjectionGuardrail` pre-hook as agents."""
    team = make_team(**_TEAM_BASE, members=[_build_member_agent('m', 'M')])
    assert team.pre_hooks is not None
    assert len(team.pre_hooks) == 1


def test_make_workflow_sets_identity_and_steps():
    """`workflow_id`, `name`, `description`, and `steps` reach the constructed workflow verbatim."""
    member = _build_member_agent('step-runner', 'Step Runner')
    step = Step(name='Run', agent=member)
    workflow = make_workflow(
        steps=[step],
        name='Research Pipeline',
        workflow_id='research-pipeline',
        description='Gather then analyse.',
    )
    assert workflow.id == 'research-pipeline'
    assert workflow.name == 'Research Pipeline'
    assert workflow.description == 'Gather then analyse.'
    assert workflow.steps == [step]


def test_make_workflow_defaults_description_to_empty_string():
    """`description` defaults to `''` so the kwarg is optional for the common case."""
    workflow = make_workflow(
        steps=[Step(name='Run', agent=_build_member_agent('runner', 'Runner'))],
        name='Pipeline',
        workflow_id='pipeline-id',
    )
    assert workflow.description == ''


def test_make_workflow_applies_workflow_defaults():
    """Entries in `WORKFLOW_DEFAULTS` reach the workflow (in-memory db, event storage on)."""
    workflow = make_workflow(
        steps=[Step(name='Run', agent=_build_member_agent('runner', 'Runner'))],
        name='Pipeline',
        workflow_id='pipeline-id',
    )
    assert workflow.db is not None
    assert workflow.store_events is True


def test_make_workflow_kwargs_override_workflow_defaults():
    """Extra `**kwargs` replace the corresponding entries in `WORKFLOW_DEFAULTS`."""
    workflow = make_workflow(
        steps=[Step(name='Run', agent=_build_member_agent('runner', 'Runner'))],
        name='Pipeline',
        workflow_id='pipeline-id',
        store_events=False,
    )
    assert workflow.store_events is False
