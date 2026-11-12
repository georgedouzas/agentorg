"""Render an in-memory `Spec` to a spec.py source file."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..core.spec import Spec
from ._models import CustomSkill, CustomTool

INDENT = '    '


def _set_fields(model: BaseModel) -> list[str]:
    """Return the fields to render: required ones and those set explicitly, so derived values stay derived."""
    fields = type(model).model_fields
    return [name for name in fields if fields[name].is_required() or name in model.model_fields_set]


def _model_classes(value: object) -> set[str]:
    """Return the class names of every model inside `value`."""
    if isinstance(value, BaseModel):
        names = {type(value).__name__}
        for name in _set_fields(value):
            names |= _model_classes(getattr(value, name))
        return names
    if isinstance(value, list | tuple):
        return set().union(*(_model_classes(item) for item in value)) if value else set()
    if isinstance(value, dict):
        return set().union(*(_model_classes(item) for item in value.values())) if value else set()
    return set()


def python_literal(value: Any, depth: int = 0) -> str:  # noqa: ANN401, PLR0911 - typed-recursive renderer
    """Render `value` as a Python expression source string suitable for embedding in spec.py.

    Pydantic models become `ClassName(field=...)` calls over their required and explicitly set fields, lists and
    dicts pretty-print with their contents rendered recursively, and functions render as their names.

    Arguments:
        value: The value to render.
        depth: Current indentation depth (number of `INDENT` units).

    Returns:
        source: A Python expression as a source string.
    """
    if isinstance(value, BaseModel):
        fields = [
            f'{INDENT * (depth + 1)}{name}={python_literal(getattr(value, name), depth + 1)}'
            for name in _set_fields(value)
        ]
        if not fields:
            return f'{type(value).__name__}()'
        return f'{type(value).__name__}(\n' + ',\n'.join(fields) + f',\n{INDENT * depth})'
    if callable(value):
        return str(value.__name__)
    if isinstance(value, list):
        if not value:
            return '[]'
        items = [f'{INDENT * (depth + 1)}{python_literal(item, depth + 1)}' for item in value]
        return '[\n' + ',\n'.join(items) + f',\n{INDENT * depth}]'
    if isinstance(value, dict):
        if not value:
            return '{}'
        items = [
            f'{INDENT * (depth + 1)}{python_literal(k, depth + 1)}: {python_literal(v, depth + 1)}'
            for k, v in value.items()
        ]
        return '{\n' + ',\n'.join(items) + f',\n{INDENT * depth}}}'
    return repr(value)


def render_spec(
    spec: Spec,
    *,
    custom_tools: Iterable[CustomTool] = (),
    custom_skills: Iterable[CustomSkill] = (),
) -> str:
    """Render a `Spec` plus its custom tools as a runnable spec.py source string.

    Custom skills are written next to spec.py by `finalize_spec`; agents reference them by name, so they need no code.

    Arguments:
        spec: The working spec.
        custom_tools: User-defined tool functions to inline above the spec.
        custom_skills: User-defined skills, accepted for symmetry with `write_spec`.

    Returns:
        source: A Python source string that, when imported, reconstructs the spec.
    """
    del custom_skills
    classes = sorted(_model_classes(spec))
    imports = 'from agentorg.core.spec import (\n' + ''.join(f'{INDENT}{name},\n' for name in classes) + ')'
    sections = [
        f'"""Spec for {spec.org.name}."""',
        imports,
        *(tool.source.strip() for tool in custom_tools),
        f'spec = {python_literal(spec)}',
    ]
    return '\n\n\n'.join(sections) + '\n'


def write_spec(
    spec: Spec,
    target: Path,
    *,
    custom_tools: Iterable[CustomTool] = (),
    custom_skills: Iterable[CustomSkill] = (),
) -> None:
    """Render `spec` with its custom tools as spec.py source and write it to `target`.

    Arguments:
        spec: The working spec to render.
        target: Destination file path.
        custom_tools: User-defined tool functions to inline above the spec.
        custom_skills: User-defined skills, written next to the file by `finalize_spec`.
    """
    target.write_text(render_spec(spec, custom_tools=custom_tools, custom_skills=custom_skills))
