"""Tests for the agent module."""

from agentorg.core.agents.framework.agno.platform._platform_engineer import agent
from agentorg.core.agents.framework.agno.platform._platform_engineer._tools import (
    check_health,
    list_env_vars,
    read_infra,
)
from agentorg.core.agents.tools import (
    get_org_parameters,
    get_setup_status,
    reset_org_parameters,
    set_org_parameter,
)


def test_agent_id_and_name():
    """The Platform Engineer carries the canonical id and display name."""
    assert agent.id == 'platform-engineer'
    assert agent.name == 'Platform Engineer'


def test_agent_has_a_role():
    """The Platform Engineer declares a non-empty role describing what it owns."""
    assert agent.role


def test_agent_tools_include_local_and_shared_callables():
    """Tools cover infra (`_tools.py`), org parameters, and setup status — drawn from both sources."""
    expected = {
        read_infra,
        list_env_vars,
        check_health,
        get_org_parameters,
        set_org_parameter,
        reset_org_parameters,
        get_setup_status,
    }
    assert set(agent.tools or []) == expected
