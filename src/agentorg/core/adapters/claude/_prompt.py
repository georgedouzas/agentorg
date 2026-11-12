"""Compile an agent definition into its system prompt."""

import json
from collections.abc import Mapping

from ...spec import Agent, Spec

TONES = {
    'direct': 'Be direct: lead with the answer and skip pleasantries.',
    'warm': 'Be warm and considerate, while staying precise.',
    'formal': 'Use a formal, professional register.',
    'playful': 'Keep a light, friendly tone without losing accuracy.',
}
VERBOSITY = {
    'terse': 'Answer in as few words as the question allows.',
    'balanced': 'Give the answer and only the context needed to act on it.',
    'thorough': 'Explain your reasoning and cover edge cases when they matter.',
}


class _Defaults(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return '{' + key + '}'


def _section(title: str, lines: list[str]) -> str:
    return f'## {title}\n\n' + '\n'.join(lines) if lines else ''


def _principles(spec: Spec, parameter_values: Mapping[str, object]) -> list[str]:
    values = _Defaults({parameter.name: parameter.default for parameter in spec.parameters} | dict(parameter_values))
    return [f'### {s.title}\n\n{s.body.format_map(values).strip()}' for s in spec.knowledge.principles.sections]


def _output(agent: Agent) -> list[str]:
    lines = []
    if agent.output.format == 'json':
        lines.append(f'Reply with a single JSON object matching this schema:\n{json.dumps(agent.output.json_schema)}')
    if agent.output.knowledge_type:
        lines.append(f"Your final answer is filed as a '{agent.output.knowledge_type}' knowledge unit.")
    return lines


def compile_system_prompt(agent: Agent, spec: Spec, parameter_values: Mapping[str, object] | None = None) -> str:
    """Compile an agent's persona, scope, org principles and output contract into one system prompt.

    Arguments:
        agent: The agent definition.
        spec: The org spec, which supplies the org name, principles and parameter defaults.
        parameter_values: Current parameter values that override the spec defaults in principle bodies.

    Returns:
        prompt: The system prompt in Markdown.
    """
    persona = agent.persona
    referrals = [
        f'- {referral.topic}: decline and refer the user to `{referral.refer_to}`.' for referral in persona.out_of_scope
    ]
    sections = [
        f'You are {agent.name}, part of {spec.org.name}. Your role: {agent.role}',
        _section('Style', [TONES[persona.tone], VERBOSITY[persona.verbosity]]),
        _section('Instructions', [persona.instructions] if persona.instructions else []),
        _section('In scope', [f'- {topic}' for topic in persona.in_scope]),
        _section('Out of scope', referrals),
        _section('Principles', _principles(spec, parameter_values or {})),
        _section('Output', _output(agent)),
    ]
    return '\n\n'.join(section for section in sections if section)
