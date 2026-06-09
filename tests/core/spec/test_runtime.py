"""Tests for runtime module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import EnvVar, EnvVars, Infra, Runtime, SetupStep

LOCAL_INFRA: dict[str, Any] = {
    'packaging': 'none',
    'database': 'sqlite',
    'vector_db': 'chromadb',
    'embedder': 'google:text-embedding-004',
    'api': 'none',
    'frontend': 'none',
    'auth': 'none',
}
DOCKER_INFRA: dict[str, Any] = {
    'packaging': 'docker',
    'database': 'postgres',
    'vector_db': 'pgvector',
    'embedder': 'openai:text-embedding-3-small',
    'api': 'none',
    'frontend': 'none',
    'auth': 'none',
}
CLOUD_INFRA: dict[str, Any] = {
    'packaging': 'docker',
    'database': 'postgres',
    'vector_db': 'pgvector',
    'embedder': 'openai:text-embedding-3-small',
    'api': 'railway',
    'frontend': 'vercel',
    'auth': 'clerk',
}
ENV_VAR: dict[str, Any] = {'name': 'GOOGLE_API_KEY', 'description': 'Gemini API key.', 'required_label': 'Prod'}
SETUP_STEP: dict[str, Any] = {
    'id': 'secrets',
    'title': 'Set keys',
    'description': 'Add the key to `.env`.',
    'variables': ['GOOGLE_API_KEY'],
}


@pytest.mark.parametrize('infra', [LOCAL_INFRA, DOCKER_INFRA, CLOUD_INFRA])
def test_valid_infra_combinations(infra: dict[str, Any]) -> None:
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


def test_embedder_must_be_provider_model() -> None:
    """`embedder` must follow the `provider:model` shape so the runtime can hand it to litellm."""
    with pytest.raises(ValidationError, match='embedder'):
        Infra(**{**LOCAL_INFRA, 'embedder': 'text-embedding-004'})


def test_infra_rejects_unknown_value() -> None:
    """Each axis is a closed `Literal`."""
    with pytest.raises(ValidationError):
        Infra(**{**LOCAL_INFRA, 'database': 'mysql'})


@pytest.mark.parametrize('missing', list(LOCAL_INFRA))
def test_infra_missing_axis_raises(missing: str) -> None:
    """Every axis is required."""
    with pytest.raises(ValidationError):
        Infra(**{k: v for k, v in LOCAL_INFRA.items() if k != missing})


def test_env_var_fields_required() -> None:
    """`EnvVar` requires name, description, and required_label."""
    var = EnvVar(**ENV_VAR)
    assert var.name == 'GOOGLE_API_KEY'
    assert var.description == 'Gemini API key.'
    assert var.required_label == 'Prod'


@pytest.mark.parametrize('missing', list(ENV_VAR))
def test_env_var_missing_field_raises(missing: str) -> None:
    """Every `EnvVar` field is required."""
    with pytest.raises(ValidationError):
        EnvVar(**{k: v for k, v in ENV_VAR.items() if k != missing})


def test_env_vars_holds_required_and_optional() -> None:
    """`EnvVars` splits declared variables into required + optional lists, coercing dicts."""
    env_vars = EnvVars(required=[EnvVar(**ENV_VAR)], optional=[])
    assert env_vars.required[0].name == 'GOOGLE_API_KEY'
    assert env_vars.optional == []


def test_env_vars_both_lists_required() -> None:
    """`required` and `optional` are both required keys (empty lists are allowed, omission is not)."""
    with pytest.raises(ValidationError):
        EnvVars(required=[EnvVar(**ENV_VAR)])  # type: ignore[call-arg]


def test_setup_step_fields() -> None:
    """`SetupStep` carries id, title, markdown description, and the variables it provides."""
    step = SetupStep(**SETUP_STEP)
    assert step.id == 'secrets'
    assert step.title == 'Set keys'
    assert step.description == 'Add the key to `.env`.'
    assert step.variables == ['GOOGLE_API_KEY']


@pytest.mark.parametrize('missing', list(SETUP_STEP))
def test_setup_step_missing_field_raises(missing: str) -> None:
    """Every `SetupStep` field is required."""
    with pytest.raises(ValidationError):
        SetupStep(**{k: v for k, v in SETUP_STEP.items() if k != missing})


def test_setup_step_with_no_variables() -> None:
    """A manual (non-auto-detectable) step declares an empty `variables` list."""
    step = SetupStep(**{**SETUP_STEP, 'variables': []})
    assert step.variables == []


def test_runtime_construction() -> None:
    """`Runtime` wraps an `Infra`, `EnvVars`, and a list of `SetupStep`."""
    runtime = Runtime(
        infra=Infra(**DOCKER_INFRA),
        env_vars=EnvVars(required=[EnvVar(**ENV_VAR)], optional=[]),
        setup=[SetupStep(**SETUP_STEP)],
    )
    assert runtime.infra.packaging == 'docker'
    assert runtime.env_vars.required[0].name == 'GOOGLE_API_KEY'
    assert runtime.setup[0].id == 'secrets'


def test_runtime_coerces_dicts() -> None:
    """`Runtime` accepts plain dicts for infra / env_vars / setup (Pydantic coercion)."""
    runtime = Runtime.model_validate(
        {
            'infra': DOCKER_INFRA,
            'env_vars': {'required': [ENV_VAR], 'optional': []},
            'setup': [SETUP_STEP],
        },
    )
    assert runtime.infra.vector_db == 'pgvector'
    assert runtime.setup[0].variables == ['GOOGLE_API_KEY']


@pytest.mark.parametrize('missing', ['infra', 'env_vars', 'setup'])
def test_runtime_missing_field_raises(missing: str) -> None:
    """`infra`, `env_vars`, and `setup` are all required on `Runtime`."""
    fields = {
        'infra': DOCKER_INFRA,
        'env_vars': {'required': [], 'optional': []},
        'setup': [],
    }
    with pytest.raises(ValidationError):
        Runtime.model_validate({k: v for k, v in fields.items() if k != missing})


def test_runtime_propagates_infra_validator() -> None:
    """An invalid `Infra` combo still raises when nested inside `Runtime`."""
    with pytest.raises(ValidationError, match='pgvector'):
        Runtime.model_validate(
            {
                'infra': {**LOCAL_INFRA, 'vector_db': 'pgvector'},
                'env_vars': {'required': [], 'optional': []},
                'setup': [],
            },
        )
