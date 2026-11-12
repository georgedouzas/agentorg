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
    admin_name: str
    admin_email: str
    visibility: Literal['public', 'private']
