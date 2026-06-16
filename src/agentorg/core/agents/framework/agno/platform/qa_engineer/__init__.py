"""The QA Engineer - runs tests and validates the spec."""

from ._agent import agent
from ._tools import run_tests, validate_spec

__all__ = ['agent', 'run_tests', 'validate_spec']
