"""Registration of agentorg's domain functions as AgentField skills."""

from typing import Any

from agentorg.core.knowledge import (
    delete_knowledge,
    list_knowledge,
    read_knowledge,
    search_knowledge,
    write_knowledge,
)
from agentorg.core.platform._backend_engineer._tools import list_agent_ids, read_agent_spec, run_tests
from agentorg.core.platform._frontend_engineer._tools import list_overview_widgets, read_ui_config
from agentorg.core.platform._platform_engineer._tools import check_health, list_env_vars, read_infra
from agentorg.core.platform._qa_engineer._tools import validate_spec
from agentorg.core.platform._security_engineer._tools import list_required_env_vars, scan_secrets
from agentorg.core.setup import get_setup_status
from agentorg.core.state import get_state, reset_state, update_state

# Each entry: (function, tags). The skill name defaults to the function name; AgentField generates
# input/output schemas from the type hints, so keeping the original signatures matters.
_SKILLS: tuple[tuple[Any, list[str]], ...] = (
    # Knowledge corpus
    (write_knowledge, ['knowledge']),
    (read_knowledge, ['knowledge']),
    (list_knowledge, ['knowledge']),
    (search_knowledge, ['knowledge']),
    (delete_knowledge, ['knowledge']),
    # Per-user org state
    (get_state, ['state']),
    (update_state, ['state']),
    (reset_state, ['state']),
    # Setup status
    (get_setup_status, ['setup']),
    # Platform: backend engineer
    (list_agent_ids, ['platform', 'backend']),
    (read_agent_spec, ['platform', 'backend']),
    (run_tests, ['platform', 'backend', 'qa']),
    # Platform: frontend engineer
    (read_ui_config, ['platform', 'frontend']),
    (list_overview_widgets, ['platform', 'frontend']),
    # Platform: platform engineer
    (read_infra, ['platform', 'infra']),
    (list_env_vars, ['platform', 'infra']),
    (check_health, ['platform', 'infra']),
    # Platform: qa engineer
    (validate_spec, ['platform', 'qa']),
    # Platform: security engineer
    (scan_secrets, ['platform', 'security']),
    (list_required_env_vars, ['platform', 'security']),
)


def register(app: Any) -> list[str]:
    """Register every domain function as an AgentField skill on `app`.

    Returns the list of registered skill names (one per function), useful for boot-time logging.
    """
    names: list[str] = []
    for fn, tags in _SKILLS:
        app.skill(tags=list(tags))(fn)
        names.append(fn.__name__)
    return names
