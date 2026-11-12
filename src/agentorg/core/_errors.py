"""Errors raised by agentorg."""

from typing import final


@final
class ConfigurationError(RuntimeError):
    """A required setting of a rendered org is missing or invalid."""
