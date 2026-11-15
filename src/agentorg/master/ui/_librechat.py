"""Run the local LibreChat stack the master interview and its live preview are chatted through."""

import secrets
import shutil
import subprocess  # nosec B404 - runs the fixed docker compose commands of the stack
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

LIBRECHAT_IMAGE = 'ghcr.io/danny-avila/librechat:v0.8.7'
COMPOSE = Path(__file__).parent / 'librechat' / 'compose.yaml'
# Byte lengths of the secrets generated on first use, not the secrets themselves.
SECRET_SIZES = {'CREDS_IV': 16} | dict.fromkeys(
    ['CHAT_API_KEY', 'CREDS_KEY', 'JWT_SECRET', 'JWT_REFRESH_SECRET', 'MEILI_MASTER_KEY'],
    32,
)
Run = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603  # nosec B603


def docker_available(run: Run = _run) -> bool:
    """Return whether a Docker daemon answers."""
    return shutil.which('docker') is not None and run(['docker', 'info']).returncode == 0


def _endpoint(name: str, port: int, models: dict[str, Any]) -> dict[str, Any]:
    return {
        'name': name,
        'apiKey': '${CHAT_API_KEY}',
        'baseURL': f'http://host.docker.internal:{port}/v1',
        'models': models,
        'titleConvo': False,
        'dropParams': ['stop', 'user', 'frequency_penalty', 'presence_penalty', 'temperature', 'top_p'],
        'headers': {
            'X-Agentorg-User-Id': '{{LIBRECHAT_USER_ID}}',
            'X-Agentorg-User-Email': '{{LIBRECHAT_USER_EMAIL}}',
            'X-Agentorg-Conversation-Id': '{{LIBRECHAT_BODY_CONVERSATIONID}}',
        },
    }


def librechat_config(master_port: int, preview_port: int) -> dict[str, Any]:
    """Return the master's LibreChat configuration: the interview and the live preview's agents.

    Arguments:
        master_port: The master server's port, which serves the `agentorg` model.
        preview_port: The preview node's port, whose agents are listed by the node.

    Returns:
        config: The `librechat.yaml` content.
    """
    off = [
        'parameters',
        'presets',
        'prompts',
        'agents',
        'memories',
        'fileSearch',
        'fileCitations',
        'runCode',
        'webSearch',
    ]
    return {
        'version': '1.3.13',
        'interface': {
            'customWelcome': 'Describe the group you want to run with agents. Type /help for the commands.',
            'modelSelect': True,
            **dict.fromkeys(off, False),
            'mcpServers': {'use': False, 'create': False},
            'marketplace': {'use': False},
        },
        'endpoints': {
            'custom': [
                _endpoint('AgentOrg', master_port, {'default': ['agentorg'], 'fetch': False}),
                # LibreChat needs one default; the list fetched from the running preview replaces it.
                _endpoint('Preview', preview_port, {'default': ['preview'], 'fetch': True}),
            ],
        },
    }


@dataclass(frozen=True)
class LibreChatStack:
    """The master's LibreChat stack in its own directory."""

    home: Path
    port: int = 3080

    @property
    def url(self) -> str:
        """Where LibreChat answers."""
        return f'http://localhost:{self.port}'

    def _env(self) -> dict[str, str]:
        path = self.home / '.env'
        if not path.exists():
            return {}
        env = {}
        for line in path.read_text().splitlines():
            key, _, value = line.partition('=')
            env[key] = value
        return env

    @property
    def chat_api_key(self) -> str:
        """The key LibreChat sends to the master and the preview."""
        return self._env()['CHAT_API_KEY']

    def prepare(self, master_port: int, preview_port: int) -> None:
        """Write the compose file, the configuration and, on first use, the secrets."""
        self.home.mkdir(parents=True, exist_ok=True)
        env = {name: secrets.token_hex(size) for name, size in SECRET_SIZES.items()} | self._env()
        env |= {'LIBRECHAT_IMAGE': LIBRECHAT_IMAGE, 'LIBRECHAT_PORT': str(self.port)}
        (self.home / '.env').write_text(''.join(f'{key}={value}\n' for key, value in sorted(env.items())))
        (self.home / '.env').chmod(0o600)
        config = librechat_config(master_port, preview_port)
        (self.home / 'librechat.yaml').write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
        shutil.copy(COMPOSE, self.home / 'compose.yaml')

    def _compose(self, *args: str, run: Run) -> None:
        result = run(['docker', 'compose', '-f', str(self.home / 'compose.yaml'), *args])
        if result.returncode:
            msg = f'docker compose {" ".join(args)} failed: {result.stderr.strip()}'
            raise RuntimeError(msg)

    def up(self, run: Run = _run) -> None:
        """Start LibreChat, MongoDB and Meilisearch in the background."""
        self._compose('up', '-d', run=run)

    def down(self, run: Run = _run) -> None:
        """Stop the stack, keeping its volumes so conversations survive."""
        self._compose('down', run=run)
