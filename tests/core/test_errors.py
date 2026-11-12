"""Tests for the errors module."""

from agentorg.core import ConfigurationError


def test_configuration_error_is_a_runtime_error() -> None:
    """Configuration errors are runtime errors that carry their message."""
    error = ConfigurationError('AMQP_URL is not set')
    assert isinstance(error, RuntimeError)
    assert str(error) == 'AMQP_URL is not set'
