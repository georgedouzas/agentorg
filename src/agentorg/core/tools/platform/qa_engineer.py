"""QA-engineer tools — run tests and validate the spec."""

import subprocess
from pathlib import Path
from typing import Any


def run_tests(cwd: str = '.') -> str:
    """Run `uv run pytest` in `cwd`.

    Returns a multi-line tail of the output.
    """
    result = subprocess.run(
        ['uv', 'run', 'pytest', '--tb=line', '-q'],  # noqa: S607
        capture_output=True,
        text=True,
        cwd=str(Path(cwd).resolve()),
        check=False,
    )
    tail = '\n'.join((result.stdout or result.stderr).strip().splitlines()[-15:])
    return f'exit={result.returncode}\n{tail}'


def _workflow_issues(workflows: list[dict[str, Any]], agent_ids: set[str]) -> list[str]:
    out: list[str] = []
    for wf in workflows:
        wid = wf.get('id', '?')
        for step in wf.get('steps') or []:
            sub_steps = step.get('parallel') or [step]
            for sub in sub_steps:
                if sub.get('agent') and sub.get('agent') not in agent_ids:
                    out.append(f'workflow {wid!r} references unknown agent {sub.get("agent")!r}')
    return out


def _team_issues(teams: list[dict[str, Any]], agent_ids: set[str]) -> list[str]:
    out: list[str] = []
    for team in teams:
        tid = team.get('id', '?')
        if team.get('leader') not in agent_ids:
            out.append(f'team {tid!r} references unknown leader {team.get("leader")!r}')
        for member in team.get('members') or []:
            if member not in agent_ids:
                out.append(f'team {tid!r} references unknown member {member!r}')
    return out


def validate_spec(
    agents: list[dict[str, Any]] | None = None,
    workflows: list[dict[str, Any]] | None = None,
    teams: list[dict[str, Any]] | None = None,
) -> str:
    """Walk the spec and report obvious structural problems (unknown agent refs etc.)."""
    agents = agents or []
    workflows = workflows or []
    teams = teams or []
    agent_ids: set[str] = {aid for a in agents if (aid := a.get('id'))}
    issues: list[str] = []
    if not agents:
        issues.append('no agents registered')
    issues += _workflow_issues(workflows, agent_ids)
    issues += _team_issues(teams, agent_ids)
    if not issues:
        return 'Spec is structurally consistent.'
    return 'Spec issues:\n' + '\n'.join(f'  - {issue}' for issue in issues)
