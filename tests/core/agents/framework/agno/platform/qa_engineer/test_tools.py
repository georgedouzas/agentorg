"""Tests for the tools module."""

from agentorg.core.agents.framework.agno.platform.qa_engineer import validate_spec

_RESEARCHER = {'id': 'researcher', 'name': 'Researcher'}
_ANALYST = {'id': 'analyst', 'name': 'Analyst'}


def test_validate_spec_reports_no_agents_registered():
    """An empty agent list is flagged — every other reference dangles without agents to anchor on."""
    result = validate_spec(agents=[], workflows=[], teams=[])
    assert 'Spec issues:' in result
    assert 'no agents registered' in result


def test_validate_spec_passes_when_everything_resolves():
    """A spec with declared agents and no broken references reports structural consistency."""
    result = validate_spec(agents=[_RESEARCHER, _ANALYST], workflows=[], teams=[])
    assert result == 'Spec is structurally consistent.'


def test_validate_spec_flags_workflow_steps_referencing_unknown_agents():
    """A workflow step whose `agent` isn't in the spec is reported with the workflow id."""
    workflows = [{'id': 'research-pipeline', 'steps': [{'agent': 'ghost-analyst'}]}]
    result = validate_spec(agents=[_RESEARCHER], workflows=workflows, teams=[])
    assert "workflow 'research-pipeline' references unknown agent 'ghost-analyst'" in result


def test_validate_spec_descends_into_parallel_workflow_steps():
    """Each entry under a `parallel` block is checked against the agent set."""
    workflows = [
        {'id': 'parallel-pipe', 'steps': [{'parallel': [{'agent': 'researcher'}, {'agent': 'ghost'}]}]},
    ]
    result = validate_spec(agents=[_RESEARCHER], workflows=workflows, teams=[])
    assert "workflow 'parallel-pipe' references unknown agent 'ghost'" in result
    # The known agent inside the same parallel block doesn't produce a phantom issue.
    assert "references unknown agent 'researcher'" not in result


def test_validate_spec_flags_teams_referencing_unknown_leader_and_members():
    """A team's `leader` and each entry in `members` must be a declared agent id."""
    teams = [{'id': 'research-team', 'leader': 'ghost-lead', 'members': ['researcher', 'ghost-member']}]
    result = validate_spec(agents=[_RESEARCHER], workflows=[], teams=teams)
    assert "team 'research-team' references unknown leader 'ghost-lead'" in result
    assert "team 'research-team' references unknown member 'ghost-member'" in result
    assert "team 'research-team' references unknown member 'researcher'" not in result


def test_validate_spec_handles_omitted_arguments():
    """Missing `agents`/`workflows`/`teams` are treated as empty lists — no crashes."""
    assert 'no agents registered' in validate_spec()
