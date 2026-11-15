"""Credit decisions: three underwriters decide an application by majority, and each recorded assessment is held."""

import threading
from collections.abc import Callable
from typing import Any

import pytest

from agentorg.core.spec import Spec

from ..conftest import Deployment
from ..harness.stub_mcp import StubLoans

SECRET = 'e2e-applications-secret'  # noqa: S105  # nosec B105 - a fake webhook secret
APPLICATION = {
    'body': (
        'Application A-7731 from a freelance designer for a 40,000 GBP unsecured loan. Declared income 18,000 GBP a '
        'year, two missed card payments in the last six months, and existing debts of 22,000 GBP. Record your '
        'assessment with record_assessment before you answer.'
    ),
}
TOOL = 'mcp__loans__record_assessment'


@pytest.mark.max_usd(2.0)
def test_credit_decisions(
    deploy: Callable[..., Deployment],
    archetype_specs: dict[str, dict[str, Any]],
    serve_stub: Callable[[StubLoans], str],
) -> None:
    """The council records all three answers and a majority decision, and every governed write waits for approval."""
    loans = StubLoans()
    url = serve_stub(loans)
    data = archetype_specs['credit-decisions']
    server = {'name': 'loans', 'transport': 'http', 'url': url}
    for agent in data['ai']['agents']:
        agent['mcp_servers'] = [server]
    org = deploy(Spec.model_validate(data), {'APPLICATIONS_SECRET': SECRET})
    client = org.client

    run_id = client.hook('applications', APPLICATION, SECRET)
    approved: list[str] = []
    done = threading.Event()

    def approve_writes() -> None:
        while not done.wait(1):
            for approval in client.approvals():
                if approval['tool_name'] == TOOL and approval['id'] not in approved:
                    approved.append(approval['id'])
                    client.decide(approval['id'], approved=True)

    approver = threading.Thread(target=approve_writes, daemon=True)
    approver.start()
    try:
        run = client.wait_for_run(run_id, timeout=600)
    finally:
        done.set()
        approver.join(10)

    assert run['status'] == 'succeeded'
    output = run['output']
    assert set(output['answers']) == {'underwriter-1', 'underwriter-2', 'underwriter-3'}
    assert output['decision'] in {'approve', 'reject'}
    assert len(approved) == len(loans.assessments) >= 1
    assert {item['status'] for item in client.approvals('approved') if item['tool_name'] == TOOL} == {'approved'}
