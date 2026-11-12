"""Tests for the operations module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import Notifications, Operations, QueueTrigger, RunsPolicy, ScheduleTrigger


def _schedule(**fields: object) -> dict[str, Any]:
    return {'kind': 'schedule', 'id': 'nightly', 'target': 'a', 'prompt': 'Go.', 'cron': '0 2 * * *', **fields}


def test_operations_defaults() -> None:
    """An empty operations block yields the documented defaults."""
    ops = Operations()
    assert (ops.runs.max_concurrent, ops.runs.retries, ops.runs.on_failure) == (4, 1, 'notify')
    assert ops.governance.approval_required == ['external_write', 'outbound_message']
    assert (ops.budget.monthly_usd, ops.budget.per_run_usd, ops.budget.alert_at) == (None, 2.0, 0.8)
    assert (ops.lifecycle.initial, ops.lifecycle.trial_max_runs) == ('trial', 50)
    assert ops.communication.max_chain_depth == 5
    assert ops.notifications.channels == ['dashboard']


def test_schedule_trigger_defaults_to_utc_skip() -> None:
    """A schedule defaults to UTC, skipping overlaps and missed fires."""
    trigger = ScheduleTrigger.model_validate(_schedule())
    assert (trigger.timezone, trigger.overlap, trigger.catch_up) == ('UTC', 'skip', 'skip')


@pytest.mark.parametrize('cron', ['not a cron', '0 2 * *', '0 2 * * * *', '61 2 * * *'])
def test_schedule_trigger_rejects_invalid_cron(cron: str) -> None:
    """Only valid 5-field cron expressions are accepted."""
    with pytest.raises(ValidationError, match='cron'):
        ScheduleTrigger.model_validate(_schedule(cron=cron))


def test_schedule_trigger_rejects_unknown_timezone() -> None:
    """The timezone must be an IANA name."""
    with pytest.raises(ValidationError, match='IANA'):
        ScheduleTrigger.model_validate(_schedule(timezone='Mars/Olympus'))


@pytest.mark.parametrize('field', [('overlap', 'merge'), ('catch_up', 'run_all')])
def test_schedule_trigger_rejects_unknown_policies(field: tuple[str, str]) -> None:
    """Overlap and catch-up are closed sets."""
    with pytest.raises(ValidationError):
        ScheduleTrigger.model_validate(_schedule(**dict([field])))


def test_operations_discriminates_trigger_kinds() -> None:
    """Triggers are parsed into the model named by `kind`."""
    ops = Operations.model_validate(
        {
            'triggers': [
                _schedule(),
                {'kind': 'event', 'id': 'on-report', 'target': 'a', 'prompt': '{event}', 'event': 'knowledge.created'},
                {'kind': 'webhook', 'id': 'helpdesk', 'target': 'a', 'prompt': '{body}', 'secret_env': 'HOOK_SECRET'},
                {'kind': 'queue', 'id': 'crm', 'target': 'a', 'prompt': '{message}', 'queue': 'crm.orders'},
            ],
        },
    )
    assert [type(trigger).__name__ for trigger in ops.triggers] == [
        'ScheduleTrigger',
        'EventTrigger',
        'WebhookTrigger',
        'QueueTrigger',
    ]


def test_event_trigger_rejects_unknown_builtin_event() -> None:
    """Event names are built-in or prefixed `custom.`."""
    with pytest.raises(ValidationError, match=r"custom\."):
        Operations.model_validate(
            {'triggers': [{'kind': 'event', 'id': 'e', 'target': 'a', 'prompt': 'Go.', 'event': 'ticket.created'}]},
        )


def test_queue_trigger_keeps_filter_and_broker_env() -> None:
    """Queue triggers carry a payload filter and an optional broker env var."""
    trigger = QueueTrigger(
        id='crm',
        target='a',
        prompt='Go.',
        queue='crm.orders',
        filter={'type': 'order'},
        url_env='CRM_AMQP',
    )
    assert (trigger.filter, trigger.url_env) == ({'type': 'order'}, 'CRM_AMQP')


def test_operations_rejects_duplicate_trigger_ids() -> None:
    """Trigger ids are unique."""
    with pytest.raises(ValidationError, match='unique'):
        Operations.model_validate({'triggers': [_schedule(), _schedule()]})


def test_runs_policy_handoff_needs_fallback_agent() -> None:
    """A handoff failure policy names the fallback agent."""
    with pytest.raises(ValidationError, match='fallback_agent'):
        RunsPolicy(on_failure='handoff')


@pytest.mark.parametrize(
    ('channel', 'field'),
    [('email', 'email_to'), ('webhook', 'webhook_url_env'), ('amqp', 'amqp_exchange')],
)
def test_notifications_channel_needs_its_destination(channel: str, field: str) -> None:
    """Each non-dashboard channel needs its destination field."""
    with pytest.raises(ValidationError, match=field):
        Notifications(channels=[channel])  # type: ignore[list-item]


def test_notifications_always_include_dashboard() -> None:
    """The dashboard channel is added when omitted."""
    assert Notifications(channels=['amqp'], amqp_exchange='ops').channels == ['dashboard', 'amqp']
