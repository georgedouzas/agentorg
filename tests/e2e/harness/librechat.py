"""Drive a LibreChat instance through the same HTTP API its web app uses."""

import json
import secrets
import uuid
from typing import Any

import httpx

# LibreChat rejects requests whose User-Agent does not look like a browser.
BROWSER = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
)
ROOT_MESSAGE = '00000000-0000-0000-0000-000000000000'


class LibreChatClient:
    """A registered and logged-in LibreChat user."""

    def __init__(self, base_url: str, email: str, name: str = 'E2E User') -> None:
        """Register `email` on the LibreChat at `base_url` and log in."""
        self.http = httpx.Client(base_url=base_url, headers={'User-Agent': BROWSER}, timeout=60)
        password = secrets.token_urlsafe(16)
        account = {'name': name, 'username': email.split('@', 1)[0], 'email': email}
        register = {**account, 'password': password, 'confirm_password': password}
        self.http.post('/api/auth/register', json=register).raise_for_status()
        login = self.http.post('/api/auth/login', json={'email': email, 'password': password})
        login.raise_for_status()
        self.http.headers['Authorization'] = f'Bearer {login.json()["token"]}'
        self.email = email

    def endpoints(self) -> dict[str, Any]:
        """Return the endpoints LibreChat offers this user."""
        reply = self.http.get('/api/endpoints')
        reply.raise_for_status()
        return reply.json()

    def chat(self, endpoint: str, model: str, text: str, conversation: str = 'new') -> str:
        """Send `text` to `model` on the custom `endpoint` and return the full reply once it finishes streaming."""
        body = {
            'text': text,
            'endpoint': endpoint,
            'endpointType': 'custom',
            'model': model,
            'spec': model,
            'conversationId': conversation,
            'parentMessageId': ROOT_MESSAGE,
            'messageId': str(uuid.uuid4()),
        }
        started = self.http.post(f'/api/agents/chat/{endpoint}', json=body)
        started.raise_for_status()
        stream = started.json()['streamId']
        with self.http.stream('GET', f'/api/agents/chat/stream/{stream}', timeout=None) as events:
            events.raise_for_status()
            for line in events.iter_lines():
                if not line.startswith('data:'):
                    continue
                event = json.loads(line.removeprefix('data:').strip() or 'null')
                if isinstance(event, dict) and event.get('final'):
                    return final_text(event)
        msg = f'LibreChat closed the stream of {stream} without a final message.'
        raise RuntimeError(msg)


def final_text(event: dict[str, Any]) -> str:
    """Return the assistant's text from LibreChat's final stream event, failing on a reported error."""
    message = event.get('responseMessage') or {}
    if message.get('error'):
        msg = f'LibreChat reported an error: {message.get("text") or message}'
        raise RuntimeError(msg)
    parts = message.get('content') or []
    text = ''.join(part.get('text', '') for part in parts if isinstance(part, dict) and part.get('type') == 'text')
    return text or str(message.get('text', ''))
