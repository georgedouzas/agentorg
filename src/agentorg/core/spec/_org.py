"""Organization metadata."""

from typing import Literal

from ._config import SpecModel


class Org(SpecModel):
    """Organization metadata model."""

    name: str
    slug: str
    package_name: str
    description: str
    repository: str
    author_name: str
    author_email: str
    visibility: Literal['public', 'private']
