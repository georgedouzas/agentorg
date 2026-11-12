"""Tests for the seed module."""

from agentorg.core.spec import Spec
from agentorg.master import PLACEHOLDER, PLACEHOLDER_NAME, PLACEHOLDER_VALUES, default_spec


def test_default_spec_is_a_validated_spec():
    """`default_spec` returns a fully-validated `Spec` (every required field has a value)."""
    spec = default_spec()
    assert isinstance(spec, Spec)


def test_default_spec_uses_recognisable_placeholders():
    """Required text fields carry placeholders the interview can later identify and replace."""
    spec = default_spec()
    assert spec.org.name == PLACEHOLDER_NAME
    # Description, admin_name etc carry friendlier seed strings now, but they all still
    # belong to PLACEHOLDER_VALUES so the interview's gate predicates still recognise them.
    assert spec.org.description in PLACEHOLDER_VALUES
    assert spec.org.repository == PLACEHOLDER
    assert spec.org.admin_name in PLACEHOLDER_VALUES


def test_default_spec_starts_with_no_agents():
    """The seed has no user-defined agents - the interview adds them via `add_or_update_agent`."""
    spec = default_spec()
    assert spec.ai.agents == []
    assert spec.ai.root is None
    assert spec.operations.budget.monthly_usd is None


def test_default_spec_has_sane_runtime_defaults():
    """Runtime fields are seeded with safe local-dev defaults (sqlite, chromadb, no packaging)."""
    spec = default_spec()
    assert spec.runtime.infra.packaging == 'none'
    assert spec.runtime.infra.database == 'sqlite'
    assert spec.runtime.infra.vector_db == 'chromadb'
    assert [var.name for var in spec.runtime.env_vars.required] == ['ANTHROPIC_API_KEY', 'AMQP_URL']
