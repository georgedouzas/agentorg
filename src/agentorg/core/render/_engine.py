"""Jinja environment + template-tree walker."""

import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _file_matches(path: Path, content: bytes) -> bool:
    """True if `path` already exists with byte-content equal to `content`."""
    try:
        return path.read_bytes() == content
    except (FileNotFoundError, OSError):
        return False


def _write_template(content: str, dest: Path) -> None:
    """Write `content` to `dest`; skip the write when the bytes match."""
    payload = content.encode('utf-8')
    if not _file_matches(dest, payload):
        dest.write_bytes(payload)


def _copy_static(source: Path, dest: Path) -> None:
    """Copy a file byte-for-byte; skip the write when the bytes match."""
    if not _file_matches(dest, source.read_bytes()):
        shutil.copy(source, dest)


def _make_env(template_dir: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(disabled_extensions=('jinja',), default=False),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=False,
    )
    env.policies['json.dumps_kwargs'] = {'ensure_ascii': False, 'sort_keys': True}
    return env


def _render_path(env: Environment, raw_path: str, data: dict[str, Any]) -> str:
    """Substitute Jinja expressions inside a file or directory name."""
    return env.from_string(raw_path).render(**data)


def render_tree(template_dir: Path, output_dir: Path, data: dict[str, Any]) -> None:
    """Walk the template tree and materialise every file (templated or static) into `output_dir`."""
    env = _make_env(template_dir)
    for path in template_dir.rglob('*'):
        raw_relative_path = path.relative_to(template_dir).as_posix()
        rendered_path = _render_path(env, raw_relative_path, data)
        relative_path = rendered_path.removesuffix('.jinja')
        if not relative_path or relative_path.endswith('/'):
            continue
        output_path = output_dir / relative_path
        if path.is_dir():
            output_path.mkdir(exist_ok=True, parents=True)
            continue
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if rendered_path.endswith('.jinja'):
            _write_template(env.get_template(raw_relative_path).render(**data), output_path)
        else:
            _copy_static(path, output_path)
