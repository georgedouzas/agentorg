"""Tests for SKILL.md validation in the sandbox module."""

import pytest

from agentorg.master import SkillValidationError, validate_skill_source

VALID_SKILL_MD = '\n'.join(
    [
        '---',
        'name: negotiation-playbook',
        'description: Steps for negotiating with a counterparty.',
        '---',
        '',
        '# Negotiation playbook',
        '',
        '1. Open with the high anchor.',
    ],
)


def test_validate_skill_source_accepts_a_well_formed_skill():
    """A clean SKILL.md with frontmatter and body passes validation."""
    validate_skill_source('negotiation-playbook', VALID_SKILL_MD)


def test_validate_skill_source_rejects_bad_name_shape():
    """The name must be lowercase-with-hyphens (the folder-name shape)."""
    with pytest.raises(SkillValidationError, match='lowercase-with-hyphens'):
        validate_skill_source('NegotiationPlaybook', VALID_SKILL_MD)


def test_validate_skill_source_rejects_missing_frontmatter():
    """Source without an opening `---` is rejected before YAML parsing."""
    body = '# A skill\n\nNo frontmatter here.'
    with pytest.raises(SkillValidationError, match='YAML frontmatter'):
        validate_skill_source('some-skill', body)


def test_validate_skill_source_rejects_unclosed_frontmatter():
    """An opening `---` without a closing `---` is rejected."""
    body = '---\nname: x\ndescription: y\n\n# Body\n'
    with pytest.raises(SkillValidationError, match='not closed'):
        validate_skill_source('some-skill', body)


def test_validate_skill_source_rejects_missing_name_field():
    """The frontmatter must declare a `name:` field."""
    body = '---\ndescription: Only a description.\n---\n\n# Body\n'
    with pytest.raises(SkillValidationError, match='name:'):
        validate_skill_source('some-skill', body)


def test_validate_skill_source_rejects_missing_description_field():
    """The frontmatter must declare a `description:` field."""
    body = '---\nname: x\n---\n\n# Body\n'
    with pytest.raises(SkillValidationError, match='description:'):
        validate_skill_source('some-skill', body)


def test_validate_skill_source_rejects_empty_body():
    """A SKILL.md with frontmatter but no body content is rejected."""
    body = '---\nname: x\ndescription: y\n---\n\n   \n\n'
    with pytest.raises(SkillValidationError, match='at least one non-empty line'):
        validate_skill_source('some-skill', body)
