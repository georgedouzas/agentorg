"""Typed client over a deployed org's public HTTP API."""

import json
import time
from dataclasses import dataclass, field
from typing import Any, TypedDict

import httpx

from agentorg.core.operations import TERMINAL, sign


class Run(TypedDict):
    """A run summary as the API returns it."""

    id: str
    target: str
    trigger_kind: str
    trigger_id: str | None
    parent_id: str | None
    status: str
    failure_reason: str | None
    output: str | None
    cost_usd: float | None


class Approval(TypedDict):
    """A pending or decided approval."""

    id: str
    run_id: str
    action_class: str
    tool_name: str
    arguments: dict[str, Any]
    status: str


@dataclass
class ChatReply:
    """The events of one streamed chat turn."""

    run_id: str | None = None
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    @property
    def end(self) -> dict[str, Any]:
        """The final `end` event's data."""
        return next(data for name, data in reversed(self.events) if name == 'end')


class OrgClient:
    """Drive a deployed org through its HTTP API."""

    def __init__(self, base_url: str, actor: str = 'e2e') -> None:
        """Connect to the org at `base_url`, deciding approvals as `actor`."""
        self.http = httpx.Client(base_url=base_url, timeout=30)
        self.actor = actor

    def _json(self, method: str, path: str, **kwargs: Any) -> Any:  # noqa: ANN401
        reply = self.http.request(method, path, **kwargs)
        reply.raise_for_status()
        return reply.json()

    def health(self) -> dict[str, Any]:
        """Return the node's broker and lifecycle health."""
        return self._json('GET', '/api/v1/health')

    def runs(self, **filters: str) -> list[Run]:
        """List runs, newest first, filtered by target, status or trigger kind."""
        return self._json('GET', '/api/v1/runs', params=filters)

    def run(self, run_id: str) -> dict[str, Any]:
        """Return one run with its prompt, transcript and child runs."""
        return self._json('GET', f'/api/v1/runs/{run_id}')

    def cancel(self, run_id: str) -> dict[str, Any]:
        """Cancel an unfinished run."""
        return self._json('POST', f'/api/v1/runs/{run_id}/cancel')

    def approvals(self, status: str = 'pending') -> list[Approval]:
        """List approvals in `status`."""
        return self._json('GET', '/api/v1/approvals', params={'status': status})

    def decide(self, approval_id: str, *, approved: bool, comment: str = '') -> dict[str, Any]:
        """Approve or reject a pending approval."""
        body = {'approved': approved, 'actor': self.actor, 'comment': comment}
        return self._json('POST', f'/api/v1/approvals/{approval_id}', json=body)

    def inbox(self) -> list[dict[str, Any]]:
        """List the inbox items waiting for a human."""
        return self._json('GET', '/api/v1/inbox')

    def lifecycle(self) -> dict[str, Any]:
        """Return the lifecycle state and its history."""
        return self._json('GET', '/api/v1/lifecycle')

    def transition(self, to: str, reason: str) -> dict[str, Any]:
        """Move the org to lifecycle state `to`."""
        return self._json('POST', '/api/v1/lifecycle', json={'to': to, 'actor': self.actor, 'reason': reason})

    def hook(self, trigger_id: str, payload: dict[str, Any], secret: str, idempotency_key: str | None = None) -> str:
        """Send a signed webhook call and return the id of the run it started."""
        body = json.dumps(payload).encode()
        headers = {'X-Agentorg-Signature': sign(secret, body), 'Content-Type': 'application/json'}
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key
        return str(self._json('POST', f'/hooks/{trigger_id}', content=body, headers=headers)['run_id'])

    def chat(self, target: str, message: str, session_id: str | None = None) -> ChatReply:
        """Send a chat message to an agent or unit and collect the streamed reply until it ends."""
        reply = ChatReply()
        body = {'message': message, 'session_id': session_id}
        with self.http.stream('POST', f'/api/v1/reasoners/{target}/stream', json=body, timeout=None) as stream:
            stream.raise_for_status()
            name = 'message'
            for line in stream.iter_lines():
                if line.startswith('event:'):
                    name = line.removeprefix('event:').strip()
                elif line.startswith('data:'):
                    data = json.loads(line.removeprefix('data:').strip())
                    reply.events.append((name, data))
                    reply.run_id = data.get('run_id', reply.run_id) if name == 'started' else reply.run_id
        return reply

    def wait_for_run(self, run_id: str, statuses: tuple[str, ...] = TERMINAL, timeout: float = 300) -> dict[str, Any]:
        """Poll a run until its status is in `statuses`, failing after `timeout` seconds."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            run = self.run(run_id)
            if run['status'] in statuses:
                return run
            time.sleep(1)
        msg = f'Run {run_id} did not reach {sorted(statuses)} within {timeout:.0f}s.'
        raise TimeoutError(msg)

    def wait_for_approval(self, run_id: str, timeout: float = 300) -> Approval:
        """Poll until the run holds a pending approval and return it."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            held = [a for a in self.approvals() if a['run_id'] == run_id]
            if held:
                return held[0]
            time.sleep(1)
        msg = f'Run {run_id} held no approval within {timeout:.0f}s.'
        raise TimeoutError(msg)

    def spent(self) -> float:
        """Return the summed cost of every run so far."""
        return sum(run['cost_usd'] or 0.0 for run in self.runs(limit='1000'))
