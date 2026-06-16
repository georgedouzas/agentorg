"""Organization metadata."""

from typing import Literal

from ._config import SpecModel


class Org(SpecModel):
    """Organization metadata model.

    The administrator's name and email live here under `admin_name` / `admin_email`. The
    rendered org's `pyproject.toml` consumes them as the package's author fields - the
    distinction is intentional, the admin is the person who configures the org, not
    necessarily the author of every downstream file.
    """

    name: str
    slug: str
    package_name: str
    description: str
    repository: str
    admin_name: str
    admin_email: str
    visibility: Literal['public', 'private']
