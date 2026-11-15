"""The infrastructure stack, environment variables, and the setup checklist."""

from typing import Literal

from pydantic import model_validator

from ._config import SpecModel


class Infra(SpecModel):
    """The infrastructure stack."""

    packaging: Literal['none', 'docker']
    database: Literal['sqlite', 'postgres']
    vector_db: Literal['chromadb', 'pgvector']
    embedder: str
    api: Literal['none', 'railway']
    frontend: Literal['none', 'vercel']
    auth: Literal['none', 'clerk']

    @model_validator(mode='after')
    def _validate_combinations(self) -> 'Infra':
        if self.vector_db == 'pgvector' and self.database != 'postgres':
            msg = "vector_db='pgvector' requires database='postgres' - pgvector is a Postgres extension."
            raise ValueError(msg)
        if self.api == 'railway' and self.packaging != 'docker':
            msg = "api='railway' requires packaging='docker' - Railway deploys the API from a Dockerfile."
            raise ValueError(msg)
        if ':' not in self.embedder:
            msg = "embedder must be 'provider:model' (e.g. 'google:text-embedding-004')."
            raise ValueError(msg)
        return self


class EnvVar(SpecModel):
    """A declared environment variable the rendered org expects."""

    name: str
    description: str
    required_label: str


class EnvVars(SpecModel):
    """Required + optional env vars the rendered org expects."""

    required: list[EnvVar]
    optional: list[EnvVar]


class SetupStep(SpecModel):
    """One item on the post-install setup checklist."""

    id: str
    title: str
    description: str
    variables: list[str]


class Runtime(SpecModel):
    """How and where the org runs; the platform env vars and the Railway setup steps are always included."""

    infra: Infra
    env_vars: EnvVars
    setup: list[SetupStep]

    @model_validator(mode='after')
    def _include_platform_requirements(self) -> 'Runtime':
        """Add the platform env vars and, on Railway, the RabbitMQ and LibreChat setup steps."""
        declared = {var.name for var in self.env_vars.required + self.env_vars.optional}
        platform = [
            EnvVar(name='ANTHROPIC_API_KEY', description='Anthropic API key of the agents.', required_label='Always'),
            EnvVar(name='AMQP_URL', description='RabbitMQ URL that carries runs and events.', required_label='Always'),
            EnvVar(
                name='CHAT_API_KEY',
                description='Key LibreChat uses to call the chat API.',
                required_label='Always',
            ),
        ]
        missing = [var for var in platform if var.name not in declared]
        if missing:
            self.env_vars.__dict__['required'] = [*missing, *self.env_vars.required]
        if self.infra.api != 'railway':
            return self
        steps = [
            SetupStep(
                id='rabbitmq',
                title='Provision RabbitMQ',
                description='Add a RabbitMQ service (Railway template or CloudAMQP) and set AMQP_URL to its URL.',
                variables=['AMQP_URL'],
            ),
            SetupStep(
                id='librechat',
                title='Deploy LibreChat',
                description=(
                    'Add a LibreChat service with MongoDB and Meilisearch, mount librechat.yaml, set AGENTORG_CHAT_URL '
                    "to the API's /v1 URL and give it the same CHAT_API_KEY."
                ),
                variables=['CHAT_API_KEY'],
            ),
        ]
        declared_steps = {step.id for step in self.setup}
        self.__dict__['setup'] = [*self.setup, *(step for step in steps if step.id not in declared_steps)]
        return self
