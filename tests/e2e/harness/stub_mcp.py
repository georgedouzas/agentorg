"""Stub MCP servers that stand in for the external systems the archetype scenarios' agents use."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# Containers reach the stubs as host.docker.internal, which DNS-rebinding protection would refuse.
SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)


class Stub(Protocol):
    """A stub system that serves an MCP server and remembers where it listens."""

    url: str

    def server(self) -> FastMCP:
        """Return the stub's MCP server."""
        ...


TICKETS: dict[str, dict[str, str]] = {
    '1042': {
        'requester': 'sam@example.com',
        'subject': 'Charged twice for November',
        'body': 'My card shows two charges of 12 GBP for the November subscription.',
    },
    '1043': {
        'requester': 'lee@example.com',
        'subject': 'Bank sync stopped',
        'body': 'My Barclays account has not synced since Monday.',
    },
    '1044': {
        'requester': 'kim@example.com',
        'subject': 'Invoice shows the wrong VAT rate',
        'body': 'My latest invoice charges 20% VAT but I am on the flat rate scheme.',
    },
}


@dataclass
class StubHelpDesk:
    """The tickets the agents can read and the replies they sent."""

    replies: list[dict[str, Any]] = field(default_factory=list)
    url: str = ''

    def server(self) -> FastMCP:
        """Return the MCP server with the `search_tickets` read tool and the `reply_ticket` outbound tool."""
        mcp = FastMCP('zendesk', stateless_http=True, json_response=True, transport_security=SECURITY)

        @mcp.tool()
        def search_tickets(query: str) -> list[dict[str, str]]:
            """Find help-desk tickets whose id, subject or body contains `query`; an empty query lists them all."""
            needle = query.lower()
            return [
                {'id': ticket_id, **ticket}
                for ticket_id, ticket in TICKETS.items()
                if needle in f'{ticket_id} {ticket["subject"]} {ticket["body"]}'.lower()
            ]

        @mcp.tool()
        def reply_ticket(ticket_id: str, body: str) -> str:
            """Send `body` to the requester of the ticket `ticket_id`."""
            self.replies.append({'ticket_id': ticket_id, 'body': body})
            return f'Reply sent on ticket {ticket_id}.'

        return mcp


@dataclass
class StubMetrics:
    """Service metrics in which `checkout` is failing, and the queries the agents made."""

    queries: list[str] = field(default_factory=list)
    url: str = ''

    def server(self) -> FastMCP:
        """Return the MCP server with the `query_metrics` read tool."""
        mcp = FastMCP('metrics', stateless_http=True, json_response=True, transport_security=SECURITY)

        @mcp.tool()
        def query_metrics(service: str = '') -> list[dict[str, Any]]:
            """Return the last hour's error rate and p95 latency of `service`, or of every service when empty."""
            self.queries.append(service)
            rows = [
                {'service': 'checkout', 'error_rate_pct': 18.4, 'p95_latency_ms': 2400},
                {'service': 'search', 'error_rate_pct': 0.3, 'p95_latency_ms': 180},
            ]
            return [row for row in rows if not service or row['service'] == service]

        return mcp


@contextmanager
def serve(stub: Stub, port: int, host: str = '127.0.0.1') -> Iterator[str]:
    """Run `stub` on `host` in a background thread and yield its MCP URL on localhost."""
    app = stub.server().streamable_http_app()
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        thread.join(0.05)
    stub.url = f'http://127.0.0.1:{port}/mcp'
    try:
        yield stub.url
    finally:
        server.should_exit = True
        thread.join(10)


@dataclass
class StubCms:
    """A content management system that remembers the articles published to it."""

    articles: list[dict[str, str]] = field(default_factory=list)
    url: str = ''

    def server(self) -> FastMCP:
        """Return the MCP server with the `publish_article` tool."""
        mcp = FastMCP('cms', stateless_http=True, json_response=True, transport_security=SECURITY)

        @mcp.tool()
        def publish_article(title: str, body: str) -> str:
            """Publish an article with `title` and markdown `body` on the website."""
            self.articles.append({'title': title, 'body': body})
            return f'Published "{title}".'

        return mcp


@dataclass
class StubLoans:
    """A loan system that remembers the underwriters' recorded assessments."""

    assessments: list[dict[str, str]] = field(default_factory=list)
    url: str = ''

    def server(self) -> FastMCP:
        """Return the MCP server with the `record_assessment` write tool."""
        mcp = FastMCP('loans', stateless_http=True, json_response=True, transport_security=SECURITY)

        @mcp.tool()
        def record_assessment(application_id: str, choice: str, reason: str) -> str:
            """Record your `approve` or `reject` assessment of an application, with a one-sentence reason."""
            self.assessments.append({'application_id': application_id, 'choice': choice, 'reason': reason})
            return f'Assessment of {application_id} recorded.'

        return mcp
