"""Tests for the writer module."""

import ast
import runpy
from pathlib import Path
from typing import Any

import pytest

from agentorg.core.spec import Agent, Spec
from agentorg.master import CustomTool, python_literal, render_spec, write_spec

ECHO_SOURCE = 'async def echo_tool(message: str) -> str:\n    """Echo."""\n    return message\n'


def _load(source: str, tmp_path: Path) -> Spec:
    path = tmp_path / 'spec.py'
    path.write_text(source)
    return runpy.run_path(str(path))['spec']


@pytest.mark.parametrize(
    'archetype',
    ['support-desk', 'research-reporting', 'ops-monitoring', 'content-pipeline', 'credit-decisions'],
)
def test_render_spec_round_trips_archetype(
    archetype_specs: dict[str, dict[str, Any]],
    archetype: str,
    tmp_path: Path,
) -> None:
    """Every archetype renders to a spec.py that reconstructs an identical spec."""
    spec = Spec.model_validate(archetype_specs[archetype])
    assert _load(render_spec(spec), tmp_path).model_dump(mode='json') == spec.model_dump(mode='json')


def test_render_spec_imports_only_agentorg_spec_models(archetype_specs: dict[str, dict[str, Any]]) -> None:
    """The rendered file imports nothing but the agentorg spec models it uses."""
    tree = ast.parse(render_spec(Spec.model_validate(archetype_specs['support-desk'])))
    imports = [node for node in tree.body if isinstance(node, ast.Import | ast.ImportFrom)]
    assert [node.module for node in imports if isinstance(node, ast.ImportFrom)] == ['agentorg.core.spec']
    names = {alias.name for node in imports for alias in node.names}
    assert {'Spec', 'Agent', 'Unit', 'WebhookTrigger', 'QueueTrigger'} <= names
    assert 'Step' not in names


def test_render_spec_inlines_custom_tools_by_name(archetype_specs: dict[str, dict[str, Any]], tmp_path: Path) -> None:
    """Custom tool sources are inlined and agents reference them by function name."""
    namespace: dict[str, Any] = {}
    exec(ECHO_SOURCE, namespace)  # noqa: S102  # nosec B102 - fixed test source
    spec_dict = archetype_specs['content-pipeline']
    spec_dict['ai']['agents'][0]['tools'] = [namespace['echo_tool']]
    source = render_spec(
        Spec.model_validate(spec_dict),
        custom_tools=[CustomTool(name='echo_tool', source=ECHO_SOURCE)],
    )
    assert 'tools=[\n' in source
    assert '                echo_tool,\n' in source
    loaded = _load(source, tmp_path)
    assert loaded.ai.agent('researcher').tools[0].__name__ == 'echo_tool'


def test_python_literal_omits_derived_fields() -> None:
    """Fields a validator derives, like default built-in tools, are not written so they stay derived."""
    rendered = python_literal(Agent(id='a', name='A', role='Works.', autonomy='read_only'))
    assert 'builtin_tools' not in rendered
    assert "autonomy='read_only'" in rendered


def test_write_spec_writes_the_rendered_source(archetype_specs: dict[str, dict[str, Any]], tmp_path: Path) -> None:
    """write_spec writes exactly what render_spec returns."""
    spec = Spec.model_validate(archetype_specs['credit-decisions'])
    write_spec(spec, tmp_path / 'spec.py')
    assert (tmp_path / 'spec.py').read_text() == render_spec(spec)
