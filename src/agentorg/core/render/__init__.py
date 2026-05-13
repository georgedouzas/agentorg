"""Render an organization from a single `spec.py` file.

Input: a directory containing `spec.py`, in which the user constructs a `Spec(...)` instance
named `spec`. The spec file may also define custom tool functions used by the agents.

Output: a project directory with:
  - The renderer's template tree (pyproject, README, frontend, factory boilerplate, ...)
    materialised against the spec's data.
  - The user's `spec.py` copied into `<output>/src/<package>/spec.py`, so the rendered
    runtime can import its agents and tools at boot.
"""

import importlib.util
import shutil
import sys
from importlib.resources import files
from pathlib import Path
from types import ModuleType
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agentorg.core.schema import Spec


def _load_spec_module(spec_path: Path) -> ModuleType:
    """Import the user's `spec.py` from disk."""
    if not spec_path.exists():
        msg = f'No spec at {spec_path}'
        raise FileNotFoundError(msg)
    module_spec = importlib.util.spec_from_file_location('_agentorg_user_spec', spec_path)
    if module_spec is None or module_spec.loader is None:
        msg = f'Cannot load spec from {spec_path}'
        raise ImportError(msg)
    module = importlib.util.module_from_spec(module_spec)
    sys.modules['_agentorg_user_spec'] = module
    module_spec.loader.exec_module(module)
    return module


def _spec_from_module(module: ModuleType) -> Spec:
    """Extract and validate the `spec` attribute from the loaded module."""
    if not hasattr(module, 'spec'):
        msg = "spec.py must define a top-level `spec` variable (instance of agentorg.core.schema.Spec)."
        raise AttributeError(msg)
    spec = module.spec
    if not isinstance(spec, Spec):
        msg = f'`spec` must be an instance of Spec, got {type(spec).__name__}.'
        raise TypeError(msg)
    return spec


def _jinja_context(spec: Spec) -> dict[str, Any]:
    """Convert the Pydantic Spec to a plain dict for Jinja consumption.

    Drops non-serialisable callables.
    """
    return spec.model_dump(mode='json', exclude={'generated': {'agents': {'__all__': {'tools'}}}})


def render(spec_dir: Path, output_dir: Path, template_dir: Path | None = None) -> None:
    """Render the project template from a spec directory.

    Args:
        spec_dir: Directory containing `spec.py`.
        output_dir: Output directory (created/overwritten in place).
        template_dir: Override the template root (defaults to the agentorg-shipped template).
    """
    spec_path = spec_dir / 'spec.py'
    user_module = _load_spec_module(spec_path)
    spec = _spec_from_module(user_module)
    data = _jinja_context(spec)

    if template_dir is None:
        template_dir = Path(str(files(__package__) / 'template'))

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

    # Drop the user's spec.py into the rendered project at <package>/spec.py so
    # the runtime can `from <package>.spec import spec` at boot.
    package_name = spec.org.package_name
    spec_dest = output_dir / 'src' / package_name / 'spec.py'
    spec_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(spec_path, spec_dest)
