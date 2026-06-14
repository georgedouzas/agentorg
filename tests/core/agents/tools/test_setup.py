"""Tests for the setup module."""

from agentorg.core.spec import SetupStep


async def test_get_setup_status(call):
    """Getting setup status."""
    llm_step = SetupStep(
        id='llm',
        title='Setup LLM',
        description='Setup the LLM for the org.',
        variables=['API_KEY', 'MODEL_NAME'],
    )
    frontend_step = SetupStep(
        id='frontend',
        title='Setup Frontend',
        description='Setup the frontend for the org.',
        variables=[],
    )
    result = await call('get_setup_status', spec_setup_steps=[llm_step.model_dump(), frontend_step.model_dump()])
    assert result == {
        'steps': [
            {
                'id': 'llm',
                'title': 'Setup LLM',
                'description': 'Setup the LLM for the org.',
                'variables': ['API_KEY', 'MODEL_NAME'],
                'completed': False,
                'missing_vars': ['API_KEY', 'MODEL_NAME'],
            },
            {
                'id': 'frontend',
                'title': 'Setup Frontend',
                'description': 'Setup the frontend for the org.',
                'variables': [],
                'completed': None,
                'missing_vars': [],
            },
        ],
        'total': 2,
        'blocked_count': 1,
        'pending_count': 1,
        'all_done': False,
    }


async def test_get_setup_status_empty(call):
    """No setup steps -> total 0, all_done False, every count zero."""
    result = await call('get_setup_status', spec_setup_steps=[])
    assert result == {
        'steps': [],
        'total': 0,
        'blocked_count': 0,
        'pending_count': 0,
        'all_done': False,
    }


async def test_get_setup_status_all_vars_set_marks_step_done(call, monkeypatch):
    """When every variable a step needs is set, the step is completed and all_done is True."""
    monkeypatch.setenv('DATABASE_URL', 'postgres://localhost:5432/agentorg')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')
    storage_step = SetupStep(
        id='storage',
        title='Configure storage backends',
        description='Point the node at a running Postgres and Redis instance.',
        variables=['DATABASE_URL', 'REDIS_URL'],
    )
    result = await call('get_setup_status', spec_setup_steps=[storage_step.model_dump()])
    assert result['steps'][0]['completed'] is True
    assert result['steps'][0]['missing_vars'] == []
    assert result['blocked_count'] == 0
    assert result['pending_count'] == 0
    assert result['all_done'] is True


async def test_get_setup_status_partial_vars_set_lists_only_missing(call, monkeypatch):
    """A step with some vars set and some missing is `completed: False` and reports only the missing ones."""
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-fixture-key')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    llm_step = SetupStep(
        id='llm-providers',
        title='Configure LLM providers',
        description='Set the API keys for the providers the org uses.',
        variables=['OPENAI_API_KEY', 'ANTHROPIC_API_KEY'],
    )
    result = await call('get_setup_status', spec_setup_steps=[llm_step.model_dump()])
    assert result['steps'][0]['completed'] is False
    assert result['steps'][0]['missing_vars'] == ['ANTHROPIC_API_KEY']
    assert result['blocked_count'] == 1
    assert result['pending_count'] == 0
    assert result['all_done'] is False


async def test_get_setup_status_envless_steps_are_pending(call):
    """Steps with no variables are unverifiable -> `completed: None`, counted as pending, all_done False."""
    steps = [
        SetupStep(
            id='db-schema',
            title='Initialize the database schema',
            description='Run `alembic upgrade head` against the configured Postgres instance.',
            variables=[],
        ).model_dump(),
        SetupStep(
            id='dashboard-deps',
            title='Install dashboard dependencies',
            description='Run `pnpm install` inside `src/frontend/` before the first `pnpm dev`.',
            variables=[],
        ).model_dump(),
    ]
    result = await call('get_setup_status', spec_setup_steps=steps)
    assert all(s['completed'] is None for s in result['steps'])
    assert result['blocked_count'] == 0
    assert result['pending_count'] == len(steps)
    assert result['all_done'] is False
