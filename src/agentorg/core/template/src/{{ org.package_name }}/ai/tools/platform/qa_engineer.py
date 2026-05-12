"""QA-engineer tools — run tests and validate the rendered spec."""

import subprocess

from ._spec import load_config, project_root


def run_tests() -> str:
    """Run the project's pytest suite.

    Returns a multi-line summary.
    """
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "pytest", "--tb=line", "-q"],  # noqa: S607
        capture_output=True,
        text=True,
        cwd=str(project_root()),
        check=False,
    )
    tail = "\n".join((result.stdout or result.stderr).strip().splitlines()[-15:])
    return f"exit={result.returncode}\n{tail}"


def validate_spec() -> str:
    """Walk the loaded config.yaml and report any obvious structural problems."""
    cfg = load_config()
    issues: list[str] = []

    agents = cfg.get("agents") or {}
    workflows = cfg.get("workflows") or []
    teams = cfg.get("teams") or []
    agent_ids = set(agents.keys())

    if not agents:
        issues.append("no agents registered")

    for wf in workflows:
        for step in wf.get("steps") or []:
            if "parallel" in step:
                for sub in step["parallel"]:
                    if sub.get("agent") not in agent_ids:
                        issues.append(f"workflow {wf.get('id', '?')!r} references unknown agent {sub.get('agent')!r}")
            elif step.get("agent") not in agent_ids:
                issues.append(f"workflow {wf.get('id', '?')!r} references unknown agent {step.get('agent')!r}")

    for team in teams:
        if team.get("leader") not in agent_ids:
            issues.append(f"team {team.get('id', '?')!r} references unknown leader {team.get('leader')!r}")
        for member in team.get("members") or []:
            if member not in agent_ids:
                issues.append(f"team {team.get('id', '?')!r} references unknown member {member!r}")

    if not issues:
        return "Spec is structurally consistent."
    return "Spec issues:\n" + "\n".join(f"  - {issue}" for issue in issues)
