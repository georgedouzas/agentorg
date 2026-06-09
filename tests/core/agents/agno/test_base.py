"""Tests for the base module."""

import pytest
from agno.skills.loaders.local import LocalSkills

from agentorg.core.agents.agno import DEFAULT_SKILLS_REFS, GitHubSkills, make_agent

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
