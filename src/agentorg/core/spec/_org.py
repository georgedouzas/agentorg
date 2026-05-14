"""Organization metadata."""

from typing import Literal

from pydantic import BaseModel


class Org(BaseModel):
    """Organization metadata model."""

    name: str
    slug: str
    package_name: str
    description: str
    repository: str
    author_name: str
    author_email: str
    visibility: Literal['public', 'private']
