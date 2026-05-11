"""Render an organization template."""

import json
import shutil
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render(agentorg: Path, output_dir: Path) -> None:
    """Render the project template.

    Args:
        agentorg: Path to agentorg.json.
        output_dir: Output directory.
    """
    data = json.loads(agentorg.read_text())
    template_dir = Path(str(files('agentorg') / 'template'))
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(disabled_extensions=('jinja',), default=False),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=False,
    )
    env.policies['json.dumps_kwargs'] = {'ensure_ascii': False, 'sort_keys': True}
    for path in template_dir.rglob('*'):
        raw_relative_path = path.relative_to(template_dir).as_posix()
        rendered_path = env.from_string(raw_relative_path).render(**data)
        relative_path = rendered_path.removesuffix('.jinja')
        if relative_path and not relative_path.endswith('/'):
            output_path = Path(output_dir) / relative_path
            if path.is_dir():
                output_path.mkdir(exist_ok=True, parents=True)
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if rendered_path.endswith('.jinja'):
                    output_path.write_text(env.get_template(raw_relative_path).render(**data))
                else:
                    shutil.copy(path, output_path)
