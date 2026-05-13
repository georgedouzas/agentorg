"""QA-engineer tools — run tests and validate the rendered spec."""

import subprocess

from ._spec import load_config, project_root


def run_tests() -> str:
    """Run the project's pytest suite.

    Returns a multi-line summary.
    """
    result = subprocess.run(
        ["uv", "run", "pytest", "--tb=line", "-q"],  # noqa: S607
        capture_output=True,
        text=True,
        cwd=str(project_root()),
        check=False,
    )
    tail = "\n".join((result.stdout or result.stderr).strip().splitlines()[-15:])
    return f"exit={result.returncode}\n{tail}"


def _workflow_issues(workflows: list[dict], agent_ids: set[str]) -> list[str]:
    out: list[str] = []
    for wf in workflows:
        wid = wf.get("id", "?")
        for step in wf.get("steps") or []:
            sub_steps = step["parallel"] if "parallel" in step else [step]
            for sub in sub_steps:
                if sub.get("agent") not in agent_ids:
                    out.append(f"workflow {wid!r} references unknown agent {sub.get('agent')!r}")
    return out


def _team_issues(teams: list[dict], agent_ids: set[str]) -> list[str]:
    out: list[str] = []
    for team in teams:
        tid = team.get("id", "?")
        if team.get("leader") not in agent_ids:
            out.append(f"team {tid!r} references unknown leader {team.get('leader')!r}")
        for member in team.get("members") or []:
            if member not in agent_ids:
                out.append(f"team {tid!r} references unknown member {member!r}")
    return out


def validate_spec() -> str:
    """Walk the loaded config.yaml and report any obvious structural problems."""
    cfg = load_config()
    agents = cfg.get("agents") or {}
    agent_ids = set(agents.keys())
    issues: list[str] = []
    if not agents:
        issues.append("no agents registered")
    issues += _workflow_issues(cfg.get("workflows") or [], agent_ids)
    issues += _team_issues(cfg.get("teams") or [], agent_ids)
    if not issues:
        return "Spec is structurally consistent."
    return "Spec issues:\n" + "\n".join(f"  - {issue}" for issue in issues)
