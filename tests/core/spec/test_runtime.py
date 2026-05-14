"""Tests for `agentorg.core.spec._runtime` — Infra, EnvVars, Runtime."""

import pytest
from pydantic import ValidationError

from agentorg.core.spec import Infra, Runtime

LOCAL_INFRA = {
    'packaging': 'none',
    'database': 'sqlite',
    'vector_db': 'chromadb',
    'api': 'none',
    'frontend': 'none',
    'auth': 'none',
}
DOCKER_INFRA = {**LOCAL_INFRA, 'packaging': 'docker', 'database': 'postgres', 'vector_db': 'pgvector'}
CLOUD_INFRA = {**DOCKER_INFRA, 'api': 'railway', 'frontend': 'vercel', 'auth': 'clerk'}


@pytest.mark.parametrize('infra', [LOCAL_INFRA, DOCKER_INFRA, CLOUD_INFRA])
def test_valid_infra_combinations(infra: dict[str, str]) -> None:
    """The local, docker, and cloud stacks all validate."""
    assert Infra(**infra)


def test_pgvector_requires_postgres() -> None:
    """`vector_db='pgvector'` with `database='sqlite'` is rejected — pgvector is a Postgres extension."""
    with pytest.raises(ValidationError, match='pgvector'):
        Infra(**{**LOCAL_INFRA, 'vector_db': 'pgvector'})


def test_railway_requires_docker() -> None:
    """`api='railway'` with `packaging='none'` is rejected — Railway deploys from a Dockerfile."""
    with pytest.raises(ValidationError, match='railway'):
        Infra(**{**DOCKER_INFRA, 'packaging': 'none', 'api': 'railway'})


def test_infra_rejects_unknown_value() -> None:
    """Each axis is a closed `Literal`."""
    with pytest.raises(ValidationError):
        Infra(**{**LOCAL_INFRA, 'database': 'mysql'})


def test_runtime_coerces_dicts() -> None:
    """`Runtime` accepts plain dicts for infra / env_vars / setup (Pydantic coercion)."""
    runtime = Runtime.model_validate(
        {
            'infra': DOCKER_INFRA,
            'env_vars': {
                'required': [{'name': 'GOOGLE_API_KEY', 'description': 'key', 'required_label': 'Prod'}],
                'optional': [],
            },
            'setup': [
                {'id': 'secrets', 'title': 'Set keys', 'vars': ['GOOGLE_API_KEY'], 'command': None, 'platform': None},
            ],
        },
    )
    assert runtime.infra.packaging == 'docker'
    assert runtime.env_vars.required[0].name == 'GOOGLE_API_KEY'
    assert runtime.setup[0].id == 'secrets'
