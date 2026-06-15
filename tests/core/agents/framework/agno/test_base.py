"""Tests for the base module."""

import pytest
from agno.skills.loaders.local import LocalSkills

from agentorg.core.agents.framework.agno import GitHubSkills, make_agent
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
    """Extra `**kwargs` replace the corresponding entries in `AGNO_DEFAULTS`."""
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
