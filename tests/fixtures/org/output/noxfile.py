"""Development tasks."""

import os
import shutil
import time
from pathlib import Path
from typing import Any

import nox
from git_changelog.cli import build_and_render

PYTHON_VERSIONS: list[str] = ['3.12', '3.13']
FILES: list[str] = ['src', 'tests', 'docs', 'noxfile.py']
_ORG_SLUG = 'org'
_RAILWAY_TEMPLATE_ID = '3jJFCA'
CHANGELOG_ARGS: dict[str, Any] = {
    'repository': '.',
    'convention': 'angular',
    'template': 'keepachangelog',
    'parse_trailers': True,
    'parse_refs': False,
    'sections': ['feat', 'fix', 'docs', 'style', 'refactor', 'tests', 'chore'],
    'bump_latest': True,
    'output': 'CHANGELOG.md',
}


def check_cli(session: nox.Session, args: list[str]) -> str:
    """Check the CLI arguments.

    Arguments:
        session: The nox session.
        args: The available CLI arguments.
    """
    available_args = ', '.join([f'`{arg}`' for arg in args])
    msg = f'Available subcommands are one of {available_args}.'
    session_args = list(session.posargs)
    if not session_args:
        session_args = ['all']
    elif len(session_args) > 1 or session_args[0] not in args:
        session.skip(f'{msg} Instead `{" ".join(session_args)}` was given')
    return session_args[0]


@nox.session
def clean(session: nox.Session) -> None:
    """Clean build artifacts and cache files.

    Arguments:
        session: The nox session.
    """
    paths = [
        '.mypy_cache',
        '.pytest_cache',
        'tests/.pytest_cache',
        'build',
        'dist',
        'htmlcov',
        'pip-wheel-metadata',
        'site',
        '__pycache__',
        'docs/generated',
        '.nox',
        '.ruff_cache',
        'uv.lock',
    ]
    for path in paths:
        shutil.rmtree(path, ignore_errors=True)
    for cache_path in Path().rglob('__pycache__'):
        shutil.rmtree(cache_path, ignore_errors=True)
    for file in Path().rglob('*.rej'):
        if file.exists():
            file.unlink()
    for file in Path().rglob('.coverage*'):
        if file.exists():
            file.unlink()


@nox.session
def docs(session: nox.Session) -> None:
    """Build or serve the documentation.

    Arguments:
        session: The nox session.
    """
    arg = check_cli(session, ['serve', 'build'])
    session.run('uv', 'sync', '--only-dev', '--active', external=True)
    session.run('mkdocs', arg)


@nox.session
@nox.parametrize('file', FILES)
def formatting(session: nox.Session, file: str) -> None:
    """Format the code.

    Arguments:
        session: The nox session.
        file: The file to be formatted.
    """
    arg = check_cli(session, ['all', 'code', 'docstrings'])
    session.run('uv', 'sync', '--only-dev', '--active', external=True)
    if arg in ['code', 'all']:
        session.run('black', file)
    if arg in ['docstrings', 'all']:
        session.run('docformatter', file)


@nox.session(python=PYTHON_VERSIONS)
@nox.parametrize('file', FILES)
def checks(session: nox.Session, file: str) -> None:
    """Check code quality, dependencies or type annotations.

    Arguments:
        session: The nox session.
        file: The file to be checked.
    """
    arg = check_cli(session, ['all', 'quality', 'dependencies', 'types', 'security', 'docs'])
    session.run('uv', 'sync', '--only-dev', '--active', external=True)
    if arg in ['quality', 'all']:
        session.run('ruff', 'check', file)
    if arg in ['types', 'all']:
        session.run('mypy', file)
    if arg in ['security', 'all']:
        session.run('bandit', '-r', file)
    if arg in ['docs', 'all'] and file == 'src':
        session.run('interrogate', file)
    if arg in ['dependencies', 'all']:
        requirements_path = (Path(session.create_tmp()) / 'requirements.txt').as_posix()
        session.run(
            'uv',
            'export',
            '--format',
            'requirements-txt',
            '--group',
            'dev',
            '--output-file',
            requirements_path,
            external=True,
        )
        session.run('safety', 'check', '-r', requirements_path, '--ignore=51457')


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    """Run tests and coverage.

    Arguments:
        session: The nox session.
    """
    session.run('uv', 'sync', '--active', external=True)
    env = {'COVERAGE_FILE': f'.coverage.{session.python}'}
    if session.posargs:
        session.run('pytest', '-n', 'auto', '-k', *session.posargs, 'tests', env=env)
    else:
        session.run('pytest', '-n', 'auto', 'tests', env=env)
    session.run('coverage', 'combine')
    session.run('coverage', 'report')
    session.run('coverage', 'html')


@nox.session
def changelog(session: nox.Session) -> None:
    """Build the changelog.

    Arguments:
        session: The nox session.
    """
    session.run('uv', 'sync', '--only-dev', '--active', external=True)
    build_and_render(**CHANGELOG_ARGS)


@nox.session(venv_backend='none')
def build(session: nox.Session) -> None:
    """Build frontend assets or Docker image.

    Arguments:
        session: The nox session.
    """
    arg = check_cli(session, ['all', 'frontend', 'image'])

    if arg in ['frontend', 'all']:
        frontend = Path('src/frontend')
        if not frontend.exists():
            session.error('src/frontend/ directory not found — run this from the repo root')
        session.log('Installing npm dependencies…')
        session.run('npm', 'ci', '--prefix', 'src/frontend', external=True)
        session.log('Building React app → public/')
        session.run('npm', 'run', 'build', '--prefix', 'src/frontend', external=True)
        api_base = os.getenv('API_BASE_URL', '')
        session.log('Frontend built → public/index.html')
        session.log(f'  API_BASE_URL : {api_base or "<empty — injected at serve time>"}')

    if arg in ['image', 'all']:
        image_name = os.getenv('IMAGE_NAME', _ORG_SLUG)
        image_tag = os.getenv('IMAGE_TAG', 'latest')
        session.run(
            'docker',
            'buildx',
            'build',
            '--platform',
            'linux/amd64,linux/arm64',
            '-t',
            f'{image_name}:{image_tag}',
            '.',
            '--push',
            external=True,
        )


@nox.session(venv_backend='none')
def deploy(session: nox.Session) -> None:
    """Deploy to Railway: PgVector database + API service + domain.

    Prerequisites: Railway CLI installed and logged in via ``railway login``.
    Reads credentials from environment or .env file.

    Arguments:
        session: The nox session.
    """
    env_file = Path('.env')
    if env_file.exists():
        for raw in env_file.read_text().splitlines():
            stripped = raw.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key, _, value = stripped.partition('=')
                os.environ.setdefault(key.strip(), value.strip())

    google_key = os.getenv('GOOGLE_API_KEY')
    if not google_key:
        session.error('GOOGLE_API_KEY not set')

    exa_key = os.getenv('EXA_API_KEY', '')
    clerk_secret = os.getenv('CLERK_SECRET_KEY', '')
    allowed_origins = os.getenv('ALLOWED_ORIGINS', '')

    if not os.getenv('CLERK_PUBLISHABLE_KEY'):
        session.warn('CLERK_PUBLISHABLE_KEY not set — auth will use localStorage UUID fallback')
    if not allowed_origins:
        session.warn('ALLOWED_ORIGINS not set — API will accept requests from all origins')

    session.run('railway', 'init', '-n', _ORG_SLUG, external=True)
    session.run('railway', 'deploy', '-t', _RAILWAY_TEMPLATE_ID, external=True)

    session.log('Waiting 10s for database...')
    time.sleep(10)

    add_cmd = [
        'railway',
        'add',
        '--service',
        _ORG_SLUG,
        '--variables',
        'DB_USER=${{pgvector.PGUSER}}',
        '--variables',
        'DB_PASS=${{pgvector.PGPASSWORD}}',
        '--variables',
        'DB_HOST=${{pgvector.PGHOST}}',
        '--variables',
        'DB_PORT=${{pgvector.PGPORT}}',
        '--variables',
        'DB_DATABASE=${{pgvector.PGDATABASE}}',
        '--variables',
        'DB_DRIVER=postgresql+psycopg',
        '--variables',
        'WAIT_FOR_DB=True',
        '--variables',
        f'GOOGLE_API_KEY={google_key}',
        '--variables',
        f'EXA_API_KEY={exa_key}',
        '--variables',
        'PORT=8000',
    ]
    if clerk_secret:
        add_cmd += ['--variables', f'CLERK_SECRET_KEY={clerk_secret}']
    if allowed_origins:
        add_cmd += ['--variables', f'ALLOWED_ORIGINS={allowed_origins}']

    session.run(*add_cmd, external=True)
    session.run('railway', 'up', '--service', _ORG_SLUG, '-d', external=True)
    session.run('railway', 'domain', '--service', _ORG_SLUG, external=True)
