"""Ops monitoring: the monitor spots a failing service and publishes an incident; the responder's failure escalates."""

from collections.abc import Callable
from typing import Any

import pytest

from agentorg.core.spec import Spec

from ..conftest import Deployment
from ..harness.client import OrgClient, Run
from ..harness.stub_mcp import StubMetrics
from ..harness.targets import wait_until

# Ten seconds before the hourly cron of 08:00 UTC, so the first scheduler ticks cross it.
CLOCK_START = '2026-11-16T07:59:50+00:00'
CHECK = (
    'Check the metrics of every service with query_metrics. If a service has an error rate above 5%, publish a '
    'custom.incident event whose payload has the service name and its error rate. Then report what you found.'
)
RESPOND = (
    'Incident: {event}. Before anything else, search the knowledge base for a runbook for this service with '
    'search_knowledge, then write the response plan.'
)


def _run_of(client: OrgClient, trigger_kind: str, target: str) -> Run:
    """Wait for the first run started by `trigger_kind` for `target` and return it."""

    def started() -> bool:
        return any(run['target'] == target for run in client.runs(trigger_kind=trigger_kind))

    wait_until(started, f'a {trigger_kind} run of {target}', timeout=300)
    return next(run for run in client.runs(trigger_kind=trigger_kind) if run['target'] == target)


@pytest.mark.max_usd(2.0)
def test_ops_monitoring(
    deploy: Callable[..., Deployment],
    archetype_specs: dict[str, dict[str, Any]],
    serve_stub: Callable[[StubMetrics], str],
) -> None:
    """The hourly check publishes `custom.incident`, the responder runs out of turns, and the failure is escalated."""
    metrics = StubMetrics()
    url = serve_stub(metrics)
    data = archetype_specs['ops-monitoring']
    agents = {agent['id']: agent for agent in data['ai']['agents']}
    agents['monitor']['mcp_servers'] = [
        {'name': 'metrics', 'transport': 'http', 'url': url, 'read_tools': ['query_metrics']},
    ]
    # One turn cannot fit the runbook search the prompt asks for, so the responder fails with max_turns.
    agents['responder']['limits'] = {'max_turns': 1}
    triggers = {trigger['id']: trigger for trigger in data['operations']['triggers']}
    triggers['hourly']['prompt'] = CHECK
    triggers['on-incident']['prompt'] = RESPOND
    org = deploy(Spec.model_validate(data), {'AGENTORG_CLOCK_START': CLOCK_START})
    client = org.client

    check = _run_of(client, 'schedule', 'monitoring')
    assert client.wait_for_run(check['id'], timeout=300)['status'] == 'succeeded'
    assert metrics.queries

    response = _run_of(client, 'event', 'response')
    assert response['trigger_id'] == 'on-incident'
    failed = client.wait_for_run(response['id'], timeout=300)
    assert (failed['status'], failed['failure_reason']) == ('failed', 'max_turns')
    wait_until(lambda: any(item['kind'] == 'escalation' for item in client.inbox()), 'the escalation', timeout=60)
    escalation = next(item for item in client.inbox() if item['kind'] == 'escalation')
    assert 'max_turns' in escalation['reason']
