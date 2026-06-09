"""The infrastructure stack, environment variables, and the setup checklist."""

from typing import Literal

from pydantic import BaseModel, model_validator


class Infra(BaseModel):
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
            msg = "vector_db='pgvector' requires database='postgres' — pgvector is a Postgres extension."
            raise ValueError(msg)
        if self.api == 'railway' and self.packaging != 'docker':
            msg = "api='railway' requires packaging='docker' — Railway deploys the API from a Dockerfile."
            raise ValueError(msg)
        if ':' not in self.embedder:
            msg = "embedder must be 'provider:model' (e.g. 'google:text-embedding-004')."
            raise ValueError(msg)
        return self


class EnvVar(BaseModel):
    """A declared environment variable the rendered org expects."""

    name: str
    description: str
    required_label: str


class EnvVars(BaseModel):
    """Required + optional env vars the rendered org expects."""

    required: list[EnvVar]
    optional: list[EnvVar]


class SetupStep(BaseModel):
    """One item on the post-install setup checklist."""

    id: str
    title: str
    description: str
    variables: list[str]


class Runtime(BaseModel):
    """How and where the org runs."""

    infra: Infra
    env_vars: EnvVars
    setup: list[SetupStep]
