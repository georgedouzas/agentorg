"""How the org takes in work, runs it, communicates, is governed and moves through its lifecycle."""

from typing import Annotated, Any, Literal
from zoneinfo import available_timezones

from croniter import croniter
from pydantic import Field, field_validator, model_validator

from ._agents import ActionClass
from ._config import SpecModel

CRON_FIELDS = 5
BUILTIN_EVENTS = frozenset(
    {
        'knowledge.created',
        'knowledge.updated',
        'run.succeeded',
        'run.failed',
        'approval.decided',
        'budget.alert',
        'lifecycle.changed',
    },
)


Channel = Literal['dashboard', 'email', 'webhook', 'amqp']


def _default_governed() -> list[ActionClass]:
    """Return the action classes governed by default."""
    return ['external_write', 'outbound_message']


def _default_channels() -> list[Channel]:
    """Return the notification channels used by default."""
    return ['dashboard']


class _TriggerBase(SpecModel):
    """Fields every trigger kind shares."""

    id: str = Field(pattern=r'^[a-z][a-z0-9-]*$')
    target: str
    prompt: str
    enabled: bool = True


class ScheduleTrigger(_TriggerBase):
    """Run the target on a cron schedule."""

    kind: Literal['schedule'] = 'schedule'
    cron: str
    timezone: str = 'UTC'
    overlap: Literal['skip', 'queue', 'allow'] = 'skip'
    catch_up: Literal['skip', 'run_once'] = 'skip'

    @field_validator('cron')
    @classmethod
    def _validate_cron(cls, value: str) -> str:
        """Accept only valid 5-field cron expressions."""
        if len(value.split()) != CRON_FIELDS or not croniter.is_valid(value):
            msg = f"cron must be a valid 5-field expression, got '{value}'."
            raise ValueError(msg)
        return value

    @field_validator('timezone')
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        """Accept only IANA timezone names."""
        if value not in available_timezones():
            msg = f"timezone must be an IANA name such as 'Europe/Athens', got '{value}'."
            raise ValueError(msg)
        return value


class EventTrigger(_TriggerBase):
    """Run the target when a matching event is published on the org bus."""

    kind: Literal['event'] = 'event'
    event: str
    filter: dict[str, Any] = Field(default_factory=dict)

    @field_validator('event')
    @classmethod
    def _validate_event(cls, value: str) -> str:
        """Accept built-in event names and `custom.*` names."""
        if value not in BUILTIN_EVENTS and not value.startswith('custom.'):
            msg = f"event must be one of {sorted(BUILTIN_EVENTS)} or start with 'custom.', got '{value}'."
            raise ValueError(msg)
        return value


class WebhookTrigger(_TriggerBase):
    """Run the target when a signed request arrives at the trigger's webhook path."""

    kind: Literal['webhook'] = 'webhook'
    secret_env: str


class QueueTrigger(_TriggerBase):
    """Run the target for each message on an external AMQP queue."""

    kind: Literal['queue'] = 'queue'
    queue: str
    filter: dict[str, Any] = Field(default_factory=dict)
    url_env: str | None = None


Trigger = Annotated[ScheduleTrigger | EventTrigger | WebhookTrigger | QueueTrigger, Field(discriminator='kind')]


class RunsPolicy(SpecModel):
    """Concurrency, retries, failure handling and retention of runs."""

    max_concurrent: int = Field(default=4, ge=1)
    retries: int = Field(default=1, ge=0)
    on_failure: Literal['notify', 'escalate', 'handoff'] = 'notify'
    fallback_agent: str | None = None
    retention_days: int = Field(default=90, ge=1)

    @model_validator(mode='after')
    def _validate_fallback(self) -> 'RunsPolicy':
        """Require a fallback agent for the handoff failure policy."""
        if self.on_failure == 'handoff' and not self.fallback_agent:
            msg = "on_failure 'handoff' needs a `fallback_agent`."
            raise ValueError(msg)
        return self


class Communication(SpecModel):
    """Bounds on chains of event-triggered runs."""

    max_chain_depth: int = Field(default=5, ge=1)


class Governance(SpecModel):
    """Which actions need human approval, who approves them and what happens on timeout."""

    approval_required: list[ActionClass] = Field(default_factory=_default_governed)
    approvers: list[str] = Field(default_factory=list)
    approval_timeout_h: float = Field(default=24, gt=0)
    on_timeout: Literal['reject', 'approve'] = 'reject'
    spend_threshold_usd: float = Field(default=1.0, gt=0)


class Budget(SpecModel):
    """The org's USD budget; an unset `monthly_usd` means the budget is not configured yet."""

    monthly_usd: float | None = Field(default=None, gt=0)
    per_run_usd: float = Field(default=2.0, gt=0)
    alert_at: float = Field(default=0.8, gt=0, le=1)
    on_exhausted: Literal['pause', 'notify_only'] = 'pause'


class Notifications(SpecModel):
    """Where notifications go; the dashboard always receives them."""

    channels: list[Channel] = Field(default_factory=_default_channels)
    email_to: list[str] = Field(default_factory=list)
    webhook_url_env: str | None = None
    amqp_exchange: str | None = None

    @model_validator(mode='after')
    def _validate_channels(self) -> 'Notifications':
        """Add the dashboard channel and require each channel's destination."""
        if 'dashboard' not in self.channels:
            self.__dict__['channels'] = ['dashboard', *self.channels]
        required = {'email': self.email_to, 'webhook': self.webhook_url_env, 'amqp': self.amqp_exchange}
        field = {'email': 'email_to', 'webhook': 'webhook_url_env', 'amqp': 'amqp_exchange'}
        for channel in self.channels:
            if channel in required and not required[channel]:
                msg = f"Notification channel '{channel}' needs `{field[channel]}`."
                raise ValueError(msg)
        return self


class Lifecycle(SpecModel):
    """The org's initial lifecycle state, trial limits and failure-rate circuit breaker."""

    initial: Literal['draft', 'trial', 'active'] = 'trial'
    trial_max_runs: int = Field(default=50, ge=1)
    max_failure_rate: float = Field(default=0.5, gt=0, le=1)
    failure_window: int = Field(default=20, ge=1)


class Operations(SpecModel):
    """Work intake, run policy, communication bounds, governance, budget, notifications and lifecycle."""

    triggers: list[Trigger] = Field(default_factory=list)
    runs: RunsPolicy = Field(default_factory=RunsPolicy)
    communication: Communication = Field(default_factory=Communication)
    governance: Governance = Field(default_factory=Governance)
    budget: Budget = Field(default_factory=Budget)
    notifications: Notifications = Field(default_factory=Notifications)
    lifecycle: Lifecycle = Field(default_factory=Lifecycle)

    @model_validator(mode='after')
    def _validate_trigger_ids(self) -> 'Operations':
        """Reject trigger ids used twice."""
        ids = [trigger.id for trigger in self.triggers]
        duplicates = sorted({id_ for id_ in ids if ids.count(id_) > 1})
        if duplicates:
            msg = f'Trigger ids must be unique; duplicated: {duplicates}.'
            raise ValueError(msg)
        return self
