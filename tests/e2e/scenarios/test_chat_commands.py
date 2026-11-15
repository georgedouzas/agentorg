"""Chat commands: a docker-packaged support desk answers `/help` and `/status` through its API and LibreChat."""

from collections.abc import Callable
from typing import Any

import pytest

from agentorg.core.spec import Spec

from ..conftest import Deployment
from ..harness.librechat import LibreChatClient

ENV = {'ZENDESK_TOKEN': 'e2e-zendesk', 'HELPDESK_SECRET': 'e2e-helpdesk'}  # nosec B105 - fake values


@pytest.mark.max_usd(0.0)
def test_chat_commands(
    deploy: Callable[..., Deployment],
    archetype_specs: dict[str, dict[str, Any]],
    request: pytest.FixtureRequest,
) -> None:
    """Commands need no model: the node answers them directly, and LibreChat relays them on docker targets."""
    spec = Spec.model_validate(archetype_specs['support-desk'])
    chat = request.config.getoption('--target') != 'local-process'
    org = deploy(spec, ENV, chat=chat)
    help_text = org.client.chat('frontline', '/help')['choices'][0]['message']['content']
    assert '/approve' in help_text
    status = org.client.chat('frontline', '/status')['choices'][0]['message']['content']
    assert 'broker: **ok**' in status
    assert org.client.runs() == []
    if not chat:
        return
    assert org.endpoints.chat is not None
    user = LibreChatClient(org.endpoints.chat, 'dana@acme.example')
    assert spec.org.name in user.endpoints()
    assert 'pending approvals: **0**' in user.chat(spec.org.name, 'frontline', '/status')
