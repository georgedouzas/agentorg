"""Tests for runtime module."""

from typing import Any

import pytest
from pydantic import ValidationError

from agentorg.core.spec import EnvVar, EnvVars, Infra, Runtime, SetupStep


def test_local_infra_validates(runtime_dict_minimal: dict[str, Any]) -> None:
    """The local (no-Docker, sqlite, chromadb) stack validates."""
    assert Infra(**runtime_dict_minimal['infra'])


def test_docker_infra_validates(runtime_dict_normal: dict[str, Any]) -> None:
    """The docker + postgres + pgvector stack validates."""
    assert Infra(**runtime_dict_normal['infra'])


def test_cloud_infra_validates(runtime_dict_normal: dict[str, Any]) -> None:
    """The cloud (Railway + Vercel + Clerk) stack validates."""
    cloud = {**runtime_dict_normal['infra'], 'api': 'railway', 'frontend': 'vercel', 'auth': 'clerk'}
    assert Infra(**cloud)


def test_pgvector_requires_postgres(runtime_dict_minimal: dict[str, Any]) -> None:
    """Pgvector requires Postgres."""
    with pytest.raises(ValidationError, match='pgvector'):
        Infra(**{**runtime_dict_minimal['infra'], 'vector_db': 'pgvector'})


def test_railway_requires_docker(runtime_dict_normal: dict[str, Any]) -> None:
    """Railway requires Docker packaging."""
    with pytest.raises(ValidationError, match='railway'):
        Infra(**{**runtime_dict_normal['infra'], 'packaging': 'none', 'api': 'railway'})


def test_embedder_must_be_provider_model(runtime_dict_minimal: dict[str, Any]) -> None:
    """Embedder follows the provider:model shape."""
    with pytest.raises(ValidationError, match='embedder'):
        Infra(**{**runtime_dict_minimal['infra'], 'embedder': 'text-embedding-004'})


def test_infra_rejects_unknown_value(runtime_dict_minimal: dict[str, Any]) -> None:
    """Each axis is a closed Literal."""
    with pytest.raises(ValidationError):
        Infra(**{**runtime_dict_minimal['infra'], 'database': 'mysql'})


@pytest.mark.parametrize(
    'missing',
    [
        'packaging',
        'database',
        'vector_db',
        'embedder',
        'api',
        'frontend',
        'auth',
    ],
)
def test_infra_missing_axis_raises(runtime_dict_minimal: dict[str, Any], missing: str) -> None:
    """Every axis is required."""
    infra = {k: v for k, v in runtime_dict_minimal['infra'].items() if k != missing}
    with pytest.raises(ValidationError):
        Infra(**infra)


def test_env_var_fields(runtime_dict_normal: dict[str, Any]) -> None:
    """Name, description, and required_label land on the model verbatim."""
    var = EnvVar(**runtime_dict_normal['env_vars']['required'][0])
    assert var.name == 'GOOGLE_API_KEY'
    assert var.required_label == 'Prod'


@pytest.mark.parametrize('missing', ['name', 'description', 'required_label'])
def test_env_var_missing_field_raises(runtime_dict_normal: dict[str, Any], missing: str) -> None:
    """Every EnvVar field is required."""
    var = dict(runtime_dict_normal['env_vars']['required'][0])
    del var[missing]
    with pytest.raises(ValidationError):
        EnvVar(**var)


def test_env_vars_holds_required_and_optional(runtime_dict_normal: dict[str, Any]) -> None:
    """EnvVars splits declared variables into required + optional."""
    env_vars = EnvVars.model_validate(runtime_dict_normal['env_vars'])
    assert env_vars.required[0].name == 'GOOGLE_API_KEY'
    assert env_vars.optional == []


def test_env_vars_both_lists_required(runtime_dict_normal: dict[str, Any]) -> None:
    """Both required and optional keys must be provided."""
    with pytest.raises(ValidationError):
        EnvVars.model_validate({'required': runtime_dict_normal['env_vars']['required']})


def test_setup_step_fields(runtime_dict_normal: dict[str, Any]) -> None:
    """SetupStep carries id, title, markdown description, and the variables it provides."""
    step = SetupStep(**runtime_dict_normal['setup'][0])
    assert step.id == 'secrets'
    assert step.variables == ['GOOGLE_API_KEY']


@pytest.mark.parametrize('missing', ['id', 'title', 'description', 'variables'])
def test_setup_step_missing_field_raises(runtime_dict_normal: dict[str, Any], missing: str) -> None:
    """Every SetupStep field is required."""
    step = dict(runtime_dict_normal['setup'][0])
    del step[missing]
    with pytest.raises(ValidationError):
        SetupStep(**step)


def test_setup_step_with_no_variables(runtime_dict_normal: dict[str, Any]) -> None:
    """A manual step declares an empty variables list."""
    step = SetupStep(**{**runtime_dict_normal['setup'][0], 'variables': []})
    assert step.variables == []


def test_runtime_construction(runtime_dict_normal: dict[str, Any]) -> None:
    """Runtime wraps an Infra, EnvVars, and a list of SetupStep."""
    runtime = Runtime.model_validate(runtime_dict_normal)
    assert runtime.infra.packaging == 'docker'
    assert [var.name for var in runtime.env_vars.required] == [
        'ANTHROPIC_API_KEY',
        'AMQP_URL',
        'CHAT_API_KEY',
        'GOOGLE_API_KEY',
    ]
    assert runtime.setup[0].id == 'secrets'


@pytest.mark.parametrize('missing', ['infra', 'env_vars', 'setup'])
def test_runtime_missing_field_raises(runtime_dict_minimal: dict[str, Any], missing: str) -> None:
    """The infra, env_vars, and setup keys are all required."""
    del runtime_dict_minimal[missing]
    with pytest.raises(ValidationError):
        Runtime.model_validate(runtime_dict_minimal)


def test_runtime_propagates_infra_validator(runtime_dict_minimal: dict[str, Any]) -> None:
    """An invalid Infra combo raises through Runtime."""
    bad = {**runtime_dict_minimal, 'infra': {**runtime_dict_minimal['infra'], 'vector_db': 'pgvector'}}
    with pytest.raises(ValidationError, match='pgvector'):
        Runtime.model_validate(bad)


def test_runtime_always_requires_platform_env_vars(runtime_dict_minimal: dict[str, Any]) -> None:
    """ANTHROPIC_API_KEY and AMQP_URL are required env vars of every org."""
    runtime = Runtime.model_validate(runtime_dict_minimal)
    assert [var.name for var in runtime.env_vars.required][:3] == ['ANTHROPIC_API_KEY', 'AMQP_URL', 'CHAT_API_KEY']


def test_runtime_does_not_duplicate_declared_platform_env_var(runtime_dict_minimal: dict[str, Any]) -> None:
    """A spec that already declares AMQP_URL keeps a single entry."""
    broker = {'name': 'AMQP_URL', 'description': 'Broker.', 'required_label': 'Prod'}
    runtime_dict_minimal['env_vars']['optional'] = [broker]
    names = [var.name for var in Runtime.model_validate(runtime_dict_minimal).env_vars.required]
    assert names == ['ANTHROPIC_API_KEY', 'CHAT_API_KEY']


def test_runtime_railway_adds_rabbitmq_and_librechat_setup_steps(runtime_dict_minimal: dict[str, Any]) -> None:
    """Railway deployments get the steps that provision RabbitMQ and deploy LibreChat."""
    runtime_dict_minimal['infra'] |= {'packaging': 'docker', 'api': 'railway'}
    steps = Runtime.model_validate(runtime_dict_minimal).setup
    assert [(step.id, step.variables) for step in steps] == [
        ('rabbitmq', ['AMQP_URL']),
        ('librechat', ['CHAT_API_KEY']),
    ]


def test_runtime_always_requires_the_chat_api_key(runtime_dict_minimal: dict[str, Any]) -> None:
    """Every org declares CHAT_API_KEY, which LibreChat uses to call the chat API."""
    names = [var.name for var in Runtime(**runtime_dict_minimal).env_vars.required]
    assert names[:3] == ['ANTHROPIC_API_KEY', 'AMQP_URL', 'CHAT_API_KEY']


def test_railway_setup_steps_are_not_duplicated(runtime_dict_normal: dict[str, Any]) -> None:
    """Validating a Railway runtime again keeps one RabbitMQ and one LibreChat step."""
    runtime_dict_normal['infra'] |= {'api': 'railway'}
    again = Runtime(**Runtime(**runtime_dict_normal).model_dump())
    assert [step.id for step in again.setup].count('librechat') == 1
