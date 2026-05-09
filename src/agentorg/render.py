"""Render a project from `project/` template + agentorg.json."""

import argparse
import json
import re
import shutil
import sys
from importlib import resources
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def _extract_vars(data: dict) -> dict:
    """Flatten agentorg.json into the full set of Jinja2 template variables."""
    org = data['org']
    deployment = data['deployment']
    return {
        'org_name': org['name'],
        'org_slug': org['slug'],
        'org_description': org['description'],
        'org_repository': org['repository'],
        'author_name': org['author_name'],
        'author_email': org['author_email'],
        'package_name': org['slug'].replace('-', '_'),
        'api_deployment': deployment.get('api', 'none'),
        'frontend_deployment': deployment.get('frontend', 'none'),
        'org_visibility': org.get('visibility', 'private'),
        'license_year': org.get('license_year', 2024),
        'org': org,
        'generated': data.get('generated', {}),
        'deployment': deployment,
        'setup': data.get('setup', {}),
    }


def _resolve_path(rel_path: str, vars: dict, env: Environment) -> tuple[str, bool] | None:
    """Render a path that may contain Jinja vars or conditionals.

    Returns (resolved_path, is_jinja) — `is_jinja` indicates whether the source filename
    ended in `.jinja` (after rendering conditionals), meaning content should be Jinja-rendered.
    Returns None when a conditional segment evaluates to empty (file is skipped).
    """
    rendered = env.from_string(rel_path).render(**vars).strip()
    if not rendered:
        return None
    parts = rendered.split('/')
    if any(not p.strip() for p in parts):
        return None
    last = parts[-1]
    is_jinja = last.endswith('.jinja')
    if is_jinja:
        parts[-1] = last[:-len('.jinja')]
    if not parts[-1].strip():
        return None
    return '/'.join(parts), is_jinja


def render(agentorg_json: Path, out_dir: Path, project_dir: Path | None = None) -> int:
    """Render the project template into `out_dir`.

    Args:
        agentorg_json: Path to agentorg.json (or a fixture directory containing it).
        out_dir: Target directory (created if missing, contents will be overwritten).
        project_dir: Override the template directory (defaults to repo `project/`).

    Returns:
        Number of files written.
    """
    if agentorg_json.is_dir():
        agentorg_json = agentorg_json / 'agentorg.json'
    data = json.loads(agentorg_json.read_text())
    vars = _extract_vars(data)

    if project_dir is None:
        # Look at the repo `project/` adjacent to this package's parent.
        project_dir = Path(__file__).resolve().parent.parent.parent / 'project'
    if not project_dir.is_dir():
        msg = f'Template directory not found: {project_dir}'
        raise FileNotFoundError(msg)

    env = Environment(
        loader=FileSystemLoader(str(project_dir)),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=False,
    )
    env.policies['json.dumps_kwargs'] = {'ensure_ascii': False, 'sort_keys': True}

    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for src in project_dir.rglob('*'):
        if not src.is_file():
            continue
        rel = src.relative_to(project_dir).as_posix()
        resolved = _resolve_path(rel, vars, env)
        if resolved is None:
            continue
        target_rel, is_jinja = resolved
        target = out_dir / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # Files whose source name ends in `.jinja` get content rendered through Jinja.
        # Everything else is copied verbatim so JSX `{{ }}` etc. survive.
        if is_jinja:
            rendered = env.get_template(rel).render(**vars)
            target.write_text(rendered)
        else:
            shutil.copyfile(src, target)
        written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    """CLI entry: `agentorg render <agentorg.json> [--out DIR]`."""
    parser = argparse.ArgumentParser(prog='agentorg render', description='Render a project from agentorg.json.')
    parser.add_argument('source', help='Path to agentorg.json (or directory containing it).')
    parser.add_argument('--out', default='out', help='Output directory (default: ./out).')
    parser.add_argument('--project', default=None, help='Override template directory (default: repo project/).')
    args = parser.parse_args(argv)

    source = Path(args.source).resolve()
    out_dir = Path(args.out).resolve()
    project = Path(args.project).resolve() if args.project else None
    n = render(source, out_dir, project)
    print(f'Rendered {n} files to {out_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
