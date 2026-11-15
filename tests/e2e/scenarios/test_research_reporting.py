"""Research reporting: a schedule fires, the lead delegates and files a report, and it starts the summariser."""

from collections.abc import Callable
from typing import Any

import pytest

from agentorg.core.spec import Spec

from ..conftest import Deployment
from ..harness.client import OrgClient, Run
from ..harness.targets import wait_until

# Ten seconds before the weekly cron of Monday 08:00 UTC, so the first scheduler ticks cross it.
CLOCK_START = '2026-11-16T07:59:50+00:00'
PROMPT = (
    'Write a short weekly research report for {now}. Ask analyst-markets and analyst-policy for one finding each, '
    'then combine them into a report of at most 150 words.'
)


def _run_of(client: OrgClient, trigger_kind: str, target: str) -> Run:
    """Wait for the first run started by `trigger_kind` for `target` and return it."""

    def started() -> bool:
        return any(run['target'] == target for run in client.runs(trigger_kind=trigger_kind))

    wait_until(started, f'a {trigger_kind} run of {target}', timeout=300)
    return next(run for run in client.runs(trigger_kind=trigger_kind) if run['target'] == target)


@pytest.mark.max_usd(3.0)
def test_research_reporting(deploy: Callable[..., Deployment], archetype_specs: dict[str, dict[str, Any]]) -> None:
    """The schedule fires at the clock start, delegation reaches both analysts, and the report starts the summariser."""
    data = archetype_specs['research-reporting']
    weekly = next(trigger for trigger in data['operations']['triggers'] if trigger['id'] == 'weekly')
    weekly['prompt'] = PROMPT
    env = {'OPS_WEBHOOK_URL': 'http://127.0.0.1:9/ops', 'AGENTORG_CLOCK_START': CLOCK_START}
    org = deploy(Spec.model_validate(data), env)
    client = org.client

    scheduled = _run_of(client, 'schedule', 'research')
    assert scheduled['trigger_id'] == 'weekly'
    report_run = client.wait_for_run(scheduled['id'], timeout=600)
    assert report_run['status'] == 'succeeded'
    delegated = {child['target'] for child in client.runs(trigger_kind='delegation')}
    assert {'analyst-markets', 'analyst-policy'} <= delegated

    reports = client.knowledge('report')
    assert len(reports) == 1
    assert reports[0]['content']

    summary = _run_of(client, 'event', 'summariser')
    assert summary['trigger_id'] == 'on-report'
    assert client.wait_for_run(summary['id'], timeout=300)['status'] == 'succeeded'
