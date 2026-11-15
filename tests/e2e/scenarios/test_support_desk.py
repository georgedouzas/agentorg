"""Support desk: tickets arrive by signed webhook and chat, and every reply waits for a human approval."""

import concurrent.futures
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from agentorg.core.spec import Spec

from ..conftest import ARTIFACTS, Deployment
from ..harness.client import Approval, OrgClient
from ..harness.librechat import LibreChatClient
from ..harness.local_docker import for_containers
from ..harness.stub_mcp import StubHelpDesk, serve
from ..harness.targets import free_port, wait_until

SECRET = 'e2e-helpdesk-secret'  # noqa: S105  # nosec B105 - a fake webhook secret
ADMIN = 'admin@acme.com'
REPLY_TOOL = 'mcp__zendesk__reply_ticket'


def _ticket(ticket_id: str) -> dict[str, str]:
    return {
        'body': (
            f'Ticket {ticket_id} needs an answer. Look it up with search_tickets, then reply to the customer on the '
            'ticket with reply_ticket: a short, friendly message saying the team is looking into it.'
        ),
    }


def _pending_reply(client: OrgClient) -> Approval:
    """Wait for the next pending approval of a ticket reply, whichever run holds it."""
    wait_until(lambda: any(a['tool_name'] == REPLY_TOOL for a in client.approvals()), 'a held ticket reply', 300)
    return next(a for a in client.approvals() if a['tool_name'] == REPLY_TOOL)


@pytest.fixture
def desk(request: pytest.FixtureRequest, listen_host: str) -> Iterator[StubHelpDesk]:
    """Serve the stub help desk where the target's node can reach it."""
    stub = StubHelpDesk()
    with serve(stub, free_port(), listen_host):
        if request.config.getoption('--target') == 'local-docker':
            stub.url = for_containers(stub.url)
        yield stub


@pytest.mark.max_usd(3.0)
def test_support_desk(
    deploy: Callable[..., Deployment],
    archetype_specs: dict[str, dict[str, Any]],
    desk: StubHelpDesk,
    request: pytest.FixtureRequest,
    run_id: str,
) -> None:
    """A webhook ticket is approved through the API, one through the Inbox, and one with `/approve` in LibreChat."""
    data = archetype_specs['support-desk']
    for agent in data['ai']['agents']:
        for server in agent.get('mcp_servers', []):
            server['url'] = desk.url
    docker = request.config.getoption('--target') == 'local-docker'
    env = {'ZENDESK_TOKEN': 'e2e-zendesk', 'HELPDESK_SECRET': SECRET}  # nosec B105 - fake values
    org = deploy(Spec.model_validate(data), env, ui=True, chat=docker)
    client = org.client

    held = client.hook('helpdesk', _ticket('1042'), SECRET)
    approval = _pending_reply(client)
    assert approval['arguments']['ticket_id'] == '1042'
    client.decide(approval['id'], approved=True)
    assert client.wait_for_run(held)['status'] == 'succeeded'
    assert [reply['ticket_id'] for reply in desk.replies] == ['1042']

    from ..harness.browser import approve_from_inbox, dashboard  # noqa: PLC0415 - Playwright loads only when needed

    held = client.hook('helpdesk', _ticket('1044'), SECRET)
    approval = _pending_reply(client)
    assert org.endpoints.ui is not None
    with dashboard(org.endpoints.ui, ARTIFACTS / run_id / 'support-desk-inbox') as page:
        approve_from_inbox(page, approval['run_id'])
    assert client.wait_for_run(held)['status'] == 'succeeded'
    assert [reply['ticket_id'] for reply in desk.replies] == ['1042', '1044']

    if not docker:
        return
    assert org.endpoints.chat is not None
    admin = LibreChatClient(org.endpoints.chat, ADMIN)
    endpoint = Spec.model_validate(data).org.name
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        reply = pool.submit(admin.chat, endpoint, 'billing', _ticket('1043')['body'])
        approval = _pending_reply(client)
        assert 'approved' in admin.chat(endpoint, 'billing', f'/approve {approval["id"]}')
        text = reply.result(timeout=600)
    assert '⏸' in text
    assert desk.replies[-1]['ticket_id'] == '1043'
