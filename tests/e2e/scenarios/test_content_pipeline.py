"""Content pipeline: the review is rejected once, approved on the rewrite, and the governed publish is approved."""

import concurrent.futures
from collections.abc import Callable
from typing import Any

import pytest

from agentorg.core.spec import Spec

from ..conftest import Deployment
from ..harness.client import Approval, OrgClient
from ..harness.stub_mcp import StubCms
from ..harness.targets import wait_until

BRIEF = (
    'Write a short article (at most 120 words) announcing that Ledgerly now exports VAT returns directly to HMRC. '
    'The publisher publishes the final text with publish_article.'
)
PUBLISH = 'mcp__cms__publish_article'
COMMENT = 'Shorten the headline to at most six words and end with a call to open the new VAT tab.'


def _review(client: OrgClient, seen: set[str]) -> Approval:
    """Wait for a pending review approval not in `seen` and return it."""

    def held() -> list[Approval]:
        return [a for a in client.approvals() if a['tool_name'].startswith('review:') and a['id'] not in seen]

    wait_until(lambda: bool(held()), 'a held review', timeout=300)
    return held()[0]


@pytest.mark.max_usd(2.0)
def test_content_pipeline(
    deploy: Callable[..., Deployment],
    archetype_specs: dict[str, dict[str, Any]],
    serve_stub: Callable[[StubCms], str],
) -> None:
    """A rejected review sends its comment to the drafter; the approved rewrite is published once that is approved."""
    cms = StubCms()
    url = serve_stub(cms)
    data = archetype_specs['content-pipeline']
    for agent in data['ai']['agents']:
        for server in agent.get('mcp_servers', []):
            server['url'] = url
    org = deploy(Spec.model_validate(data), {'CMS_TOKEN': 'e2e-cms'})  # nosec B105 - a fake token
    client = org.client

    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        reply = pool.submit(client.chat, 'content', BRIEF)
        first = _review(client, set())
        assert first['tool_name'] == 'review:2:drafter'
        client.decide(first['id'], approved=False, comment=COMMENT)
        second = _review(client, {first['id']})
        client.decide(second['id'], approved=True)
        # Writes to the CMS are governed by default, so the publish waits for its own approval.
        wait_until(lambda: any(a['tool_name'] == PUBLISH for a in client.approvals()), 'the held publish', 300)
        publish = next(a for a in client.approvals() if a['tool_name'] == PUBLISH)
        client.decide(publish['id'], approved=True)
        content = reply.result(timeout=600)['choices'][0]['message']['content']

    run = client.runs(target='content')[0]
    assert client.wait_for_run(run['id'])['status'] == 'succeeded'
    assert content
    drafts = client.runs(target='drafter')
    assert len(drafts) == 2
    assert COMMENT in client.run(drafts[0]['id'])['prompt']
    assert len(cms.articles) == 1
