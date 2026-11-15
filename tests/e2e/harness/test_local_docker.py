"""Self-tests of the local-docker target's compose and Dockerfile adaptation, and of the LibreChat stream parsing."""

from typing import Any

import pytest

from .librechat import final_text
from .local_docker import DOCKERFILE, adapt_compose, adapt_dockerfile, for_containers

COMPOSE: dict[str, Any] = {
    'services': {
        'rabbitmq': {'image': 'rabbitmq', 'container_name': 'desk-rabbitmq', 'ports': ['5672:5672', '15672:15672']},
        'desk-api': {
            'build': {'context': '.', 'dockerfile': 'Dockerfile'},
            'image': 'desk:latest',
            'container_name': 'desk-api',
            'command': 'uvicorn desk.app.main:app --host 0.0.0.0 --port 8000 --reload',
            'ports': ['8000:8000'],
            'volumes': ['.:/app'],
            'environment': ['RUNTIME_ENV=dev', 'AMQP_URL=amqp://rabbitmq'],
        },
    },
    'volumes': {'pgdata': None},
}


def test_compose_isolates_names_ports_and_the_api_image() -> None:
    """Names and host ports go, the API runs its built image with the run's environment."""
    adapted = adapt_compose(COMPOSE, 'desk', {'ANTHROPIC_BASE_URL': 'http://127.0.0.1:9000'}, 'run-api:latest')
    broker, api = adapted['services']['rabbitmq'], adapted['services']['desk-api']
    assert 'container_name' not in broker
    assert broker['ports'] == ['127.0.0.1::5672', '127.0.0.1::15672']
    assert (api['image'], api['build']['dockerfile']) == ('run-api:latest', DOCKERFILE)
    assert 'volumes' not in api
    assert '--reload' not in api['command']
    assert api['environment'] == {
        'RUNTIME_ENV': 'dev',
        'AMQP_URL': 'amqp://rabbitmq',
        'ANTHROPIC_BASE_URL': 'http://host.docker.internal:9000',
    }
    assert adapted['volumes'] == {'pgdata': None}
    assert COMPOSE['services']['desk-api']['volumes'] == ['.:/app']


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('http://127.0.0.1:9000', 'http://host.docker.internal:9000'),
        ('http://localhost/v1', 'http://host.docker.internal/v1'),
        ('https://api.anthropic.com', 'https://api.anthropic.com'),
        ('e2e-chat-key', 'e2e-chat-key'),
    ],
)
def test_loopback_urls_are_rewritten_for_containers(value: str, expected: str) -> None:
    """Only URLs on the host's loopback change."""
    assert for_containers(value) == expected


def test_dockerfile_installs_the_local_wheel_first() -> None:
    """The wheel is installed before the org's own package, and a changed Dockerfile is reported."""
    dockerfile = 'WORKDIR /app\nRUN uv pip install --system -e .\n'
    adapted = adapt_dockerfile(dockerfile)
    assert adapted.index('wheels/*.whl') < adapted.index('--system -e .')
    assert 'UV_CONSTRAINT=' in adapted
    with pytest.raises(ValueError, match='no longer installs'):
        adapt_dockerfile('RUN pip install .\n')


def test_final_text_joins_text_parts_and_reports_errors() -> None:
    """The final event's text parts make the reply; an error message raises."""
    content = [{'type': 'text', 'text': 'Lifecycle: '}, {'type': 'think', 'text': 'x'}, {'type': 'text', 'text': 'ok'}]
    assert final_text({'final': True, 'responseMessage': {'content': content}}) == 'Lifecycle: ok'
    assert final_text({'final': True, 'responseMessage': {'text': 'plain'}}) == 'plain'
    with pytest.raises(RuntimeError, match='reported an error'):
        final_text({'final': True, 'responseMessage': {'error': True, 'text': 'boom'}})
