"""Org instance parameters - the configurable knobs that distinguish one org instance from another."""

from typing import Any, Literal

from ._config import SpecModel


class Parameter(SpecModel):
    """A single user-tunable org instance parameter."""

    name: str
    type: Literal['int', 'float', 'string', 'bool', 'object', 'array']
    default: Any
    label: str
    format: str | None
