"""Tests for the prompt module."""

from typing import Any

from agentorg.core.adapters.claude import compile_system_prompt
from agentorg.core.spec import Spec


def _spec(spec_dict_minimal: dict[str, Any], **agent: Any) -> Spec:
    spec_dict_minimal['ai']['agents'][0].update(agent)
    spec_dict_minimal['ai']['agents'].append({'id': 'finance', 'name': 'Finance', 'role': 'Handles billing.'})
    spec_dict_minimal['ai']['root'] = {
        'id': 'org',
        'name': 'Org',
        'model': 'hub',
        'lead': 'assistant',
        'members': ['finance'],
    }
    spec_dict_minimal['parameters'] = [
        {'name': 'domain_focus', 'type': 'string', 'default': 'Applied Research', 'label': 'Focus', 'format': None},
    ]
    spec_dict_minimal['knowledge']['principles']['sections'] = [
        {'id': 'focus', 'title': 'Focus', 'body': 'Stay within {domain_focus}. Cite {unknown_placeholder}.'},
    ]
    return Spec.model_validate(spec_dict_minimal)


def test_compile_system_prompt_states_identity_and_style(spec_dict_minimal: dict[str, Any]) -> None:
    """The prompt names the agent, the org and its role, and states tone and verbosity."""
    spec = _spec(spec_dict_minimal, persona={'tone': 'formal', 'verbosity': 'terse'})
    prompt = compile_system_prompt(spec.ai.agent('assistant'), spec)
    assert prompt.startswith('You are Assistant, part of Acme. Your role: Answers questions.')
    assert 'formal, professional register' in prompt
    assert 'as few words' in prompt


def test_compile_system_prompt_lists_referrals(spec_dict_minimal: dict[str, Any]) -> None:
    """Out-of-scope topics name the agent to refer to."""
    spec = _spec(spec_dict_minimal, persona={'out_of_scope': [{'topic': 'billing', 'refer_to': 'finance'}]})
    prompt = compile_system_prompt(spec.ai.agent('assistant'), spec)
    assert '- billing: decline and refer the user to `finance`.' in prompt


def test_compile_system_prompt_substitutes_parameters(spec_dict_minimal: dict[str, Any]) -> None:
    """Principle placeholders take parameter defaults, overrides win, and unknown placeholders stay literal."""
    spec = _spec(spec_dict_minimal)
    default_prompt = compile_system_prompt(spec.ai.agent('assistant'), spec)
    override_prompt = compile_system_prompt(spec.ai.agent('assistant'), spec, {'domain_focus': 'Climate'})
    assert 'Stay within Applied Research.' in default_prompt
    assert 'Stay within Climate.' in override_prompt
    assert '{domain_focus}' not in default_prompt
    assert '{unknown_placeholder}' in default_prompt


def test_compile_system_prompt_states_output_contract(spec_dict_minimal: dict[str, Any]) -> None:
    """JSON output and the knowledge type are spelled out."""
    spec_dict_minimal['knowledge']['types'] = [{'id': 'report', 'label': 'Reports', 'metadata_fields': []}]
    output = {'format': 'json', 'json_schema': {'type': 'object'}, 'knowledge_type': 'report'}
    spec = _spec(spec_dict_minimal, output=output)
    prompt = compile_system_prompt(spec.ai.agent('assistant'), spec)
    assert 'single JSON object matching this schema:\n{"type": "object"}' in prompt
    assert "filed as a 'report' knowledge unit" in prompt


def test_compile_system_prompt_omits_empty_sections(spec_dict_minimal: dict[str, Any]) -> None:
    """Sections with nothing to say are left out."""
    spec = Spec.model_validate(spec_dict_minimal)
    prompt = compile_system_prompt(spec.ai.agent('assistant'), spec)
    assert '## Instructions' not in prompt
    assert '## Out of scope' not in prompt
