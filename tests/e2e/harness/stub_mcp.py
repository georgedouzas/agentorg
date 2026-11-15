"""A stub help-desk MCP server the support-desk scenario's agents search and reply through."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

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
        # Containers reach the stub as host.docker.internal, which DNS-rebinding protection would refuse.
        security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
        mcp = FastMCP('zendesk', stateless_http=True, json_response=True, transport_security=security)

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


@contextmanager
def serve(desk: StubHelpDesk, port: int, host: str = '127.0.0.1') -> Iterator[str]:
    """Run `desk` on `host` in a background thread and yield its MCP URL on localhost."""
    app = desk.server().streamable_http_app()
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        thread.join(0.05)
    desk.url = f'http://127.0.0.1:{port}/mcp'
    try:
        yield desk.url
    finally:
        server.should_exit = True
        thread.join(10)
