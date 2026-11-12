"""Shared fixtures for the agentorg test suite, including the archetype org specs."""

from typing import Any

import pytest

HELPDESK_VAR = 'HELPDESK_SECRET'
APPLICATIONS_VAR = 'APPLICATIONS_SECRET'
CHOICE_OUTPUT: dict[str, Any] = {
    'format': 'json',
    'json_schema': {
        'type': 'object',
        'properties': {'choice': {'enum': ['approve', 'reject']}, 'reason': {'type': 'string'}},
    },
}


def _agent(agent_id: str, role: str, **fields: object) -> dict[str, Any]:
    return {'id': agent_id, 'name': agent_id.replace('-', ' ').title(), 'role': role, **fields}


def _spec(
    slug: str,
    ai: dict[str, Any],
    operations: dict[str, Any],
    env: list[str],
    types: list[str],
) -> dict[str, Any]:
    return {
        'org': {
            'name': slug.replace('-', ' ').title(),
            'slug': slug,
            'package_name': slug.replace('-', '_'),
            'description': f'The {slug} archetype.',
            'repository': f'https://github.com/acme/{slug}',
            'admin_name': 'Admin',
            'admin_email': 'admin@acme.com',
            'visibility': 'private',
        },
        'runtime': {
            'infra': {
                'packaging': 'docker',
                'database': 'postgres',
                'vector_db': 'pgvector',
                'embedder': 'openai:text-embedding-3-small',
                'api': 'none',
                'frontend': 'none',
                'auth': 'none',
            },
            'env_vars': {
                'required': [{'name': name, 'description': name, 'required_label': 'Prod'} for name in env],
                'optional': [],
            },
            'setup': [],
        },
        'ai': ai,
        'operations': operations,
        'parameters': [],
        'knowledge': {
            'principles': {'sections': [{'id': 'care', 'title': 'Care', 'body': 'Be accurate.'}]},
            'types': [{'id': type_id, 'label': type_id.title(), 'metadata_fields': []} for type_id in types],
        },
        'ui': {
            'app': {'name': slug, 'icon': '🏢', 'description': ''},
            'empty_state': {'icon': '🏢', 'title': 'Pick an agent', 'body': ''},
            'knowledge_empty': '',
            'agent_groups': [],
            'workflow_groups': [],
            'featured_agents': [],
            'agent_icons': {},
            'overview': [],
            'agent_configs': {},
            'chat_quick_prompts': {},
        },
    }


def _support_desk() -> dict[str, Any]:
    zendesk = {
        'name': 'zendesk',
        'transport': 'http',
        'url': 'https://zendesk.example/mcp',
        'env': ['ZENDESK_TOKEN'],
        'read_tools': ['search_tickets'],
        'outbound_tools': ['reply_ticket'],
    }
    ai = {
        'agents': [
            _agent('desk-lead', 'Owns escalations for the support desk.', model='opus'),
            _agent('triage', 'Classifies tickets and hands them off.', model='haiku', autonomy='read_only'),
            _agent('billing', 'Resolves billing tickets.', autonomy='act', mcp_servers=[zendesk], tags=['billing']),
            _agent('tech', 'Resolves technical tickets.', autonomy='act', mcp_servers=[zendesk], tags=['tech']),
        ],
        'root': {
            'id': 'support',
            'name': 'Support',
            'model': 'hub',
            'lead': 'desk-lead',
            'members': [
                {
                    'id': 'frontline',
                    'name': 'Frontline',
                    'model': 'pool',
                    'lead': 'triage',
                    'members': ['billing', 'tech'],
                },
            ],
        },
    }
    operations = {
        'triggers': [
            {
                'kind': 'webhook',
                'id': 'helpdesk',
                'target': 'frontline',
                'prompt': 'New ticket: {body}',
                'secret_env': HELPDESK_VAR,
            },
            {
                'kind': 'queue',
                'id': 'crm',
                'target': 'frontline',
                'prompt': 'CRM case: {message}',
                'queue': 'crm.cases',
            },
        ],
        'budget': {'monthly_usd': 500},
    }
    return _spec('support-desk', ai, operations, ['ZENDESK_TOKEN', 'HELPDESK_SECRET'], [])


def _research_reporting() -> dict[str, Any]:
    ai = {
        'agents': [
            _agent(
                'lead-analyst',
                'Plans research and writes the report.',
                model='opus',
                output={'knowledge_type': 'report'},
            ),
            _agent('analyst-markets', 'Researches markets.', autonomy='read_only'),
            _agent('analyst-policy', 'Researches policy.', autonomy='read_only'),
            _agent('summariser', 'Summarises new reports.', model='haiku'),
        ],
        'root': {
            'id': 'research',
            'name': 'Research',
            'model': 'hub',
            'lead': 'lead-analyst',
            'members': ['analyst-markets', 'analyst-policy', 'summariser'],
        },
    }
    operations = {
        'triggers': [
            {
                'kind': 'schedule',
                'id': 'weekly',
                'target': 'research',
                'prompt': 'Write the weekly report for {now}.',
                'cron': '0 8 * * MON',
            },
            {
                'kind': 'event',
                'id': 'on-report',
                'target': 'summariser',
                'prompt': 'Summarise: {event}',
                'event': 'knowledge.created',
                'filter': {'type': 'report'},
            },
        ],
        'budget': {'monthly_usd': 300},
        'notifications': {'channels': ['webhook'], 'webhook_url_env': 'OPS_WEBHOOK_URL'},
    }
    return _spec('research-reporting', ai, operations, ['OPS_WEBHOOK_URL'], ['report'])


def _ops_monitoring() -> dict[str, Any]:
    metrics = {'name': 'metrics', 'transport': 'stdio', 'command': 'metrics-mcp', 'read_tools': ['query_metrics']}
    ai = {
        'agents': [
            _agent('ops-lead', 'Coordinates incident response.'),
            _agent(
                'monitor',
                'Watches metrics for anomalies.',
                model='haiku',
                autonomy='read_only',
                mcp_servers=[metrics],
            ),
            _agent('responder', 'Responds to incidents.', autonomy='act'),
        ],
        'root': {
            'id': 'ops',
            'name': 'Ops',
            'model': 'hub',
            'lead': 'ops-lead',
            'members': [
                {'id': 'monitoring', 'name': 'Monitoring', 'model': 'solo', 'members': ['monitor']},
                {'id': 'response', 'name': 'Response', 'model': 'solo', 'members': ['responder']},
            ],
        },
    }
    operations = {
        'triggers': [
            {
                'kind': 'schedule',
                'id': 'hourly',
                'target': 'monitoring',
                'prompt': 'Check the metrics.',
                'cron': '0 * * * *',
            },
            {
                'kind': 'event',
                'id': 'on-incident',
                'target': 'response',
                'prompt': 'Incident: {event}',
                'event': 'custom.incident',
            },
        ],
        'runs': {'on_failure': 'escalate'},
        'budget': {'monthly_usd': 150},
        'notifications': {'channels': ['amqp'], 'amqp_exchange': 'oncall'},
    }
    return _spec('ops-monitoring', ai, operations, [], [])


def _content_pipeline() -> dict[str, Any]:
    cms = {'name': 'cms', 'transport': 'http', 'url': 'https://cms.example/mcp', 'env': ['CMS_TOKEN']}
    ai = {
        'agents': [
            _agent('researcher', 'Collects material for the piece.', autonomy='read_only'),
            _agent('drafter', 'Drafts the piece.'),
            _agent('publisher', 'Publishes the approved piece.', autonomy='act', mcp_servers=[cms]),
        ],
        'root': {
            'id': 'content',
            'name': 'Content',
            'model': 'pipeline',
            'members': ['researcher', {'member': 'drafter', 'review': 'human'}, 'publisher'],
        },
    }
    operations = {'budget': {'monthly_usd': 100}}
    return _spec('content-pipeline', ai, operations, ['CMS_TOKEN'], [])


def _credit_decisions() -> dict[str, Any]:
    ai = {
        'agents': [
            _agent(f'underwriter-{i}', 'Assesses credit applications.', output=CHOICE_OUTPUT) for i in (1, 2, 3)
        ],
        'root': {
            'id': 'credit-board',
            'name': 'Credit Board',
            'model': 'council',
            'decision': 'majority',
            'members': ['underwriter-1', 'underwriter-2', 'underwriter-3'],
        },
    }
    operations = {
        'triggers': [
            {
                'kind': 'webhook',
                'id': 'applications',
                'target': 'credit-board',
                'prompt': 'Application: {body}',
                'secret_env': APPLICATIONS_VAR,
            },
        ],
        'governance': {'approval_required': ['external_write', 'outbound_message', 'spend']},
        'budget': {'monthly_usd': 250},
    }
    return _spec('credit-decisions', ai, operations, ['APPLICATIONS_SECRET'], [])


@pytest.fixture
def archetype_specs() -> dict[str, dict[str, Any]]:
    """Spec dicts for the five org archetypes, keyed by name."""
    return {
        'support-desk': _support_desk(),
        'research-reporting': _research_reporting(),
        'ops-monitoring': _ops_monitoring(),
        'content-pipeline': _content_pipeline(),
        'credit-decisions': _credit_decisions(),
    }
