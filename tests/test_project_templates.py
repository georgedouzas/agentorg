"""End-to-end test: render each fixture and assert byte-identity against fixture output.

`agentorg.render.render` walks `project/`, renders Jinja templates, and copies the rest
verbatim. The fixture's `output/` directory is the golden snapshot; this test diffs
every file the renderer produces against that snapshot.

Files that exist in the fixture but are NOT produced by the renderer (per-agent `.py`,
per-workflow `.py`, org-specific tools, `CLAUDE.md`, `.env`, `node_modules/`, `uv.lock`)
are out of scope — those are written by the metaagent later or are runtime artifacts.
"""

import shutil
from pathlib import Path

import pytest

from agentorg.render import render

REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / 'fixtures'
FIXTURES = ['investment-team', 'eng-team']


@pytest.mark.parametrize('fixture_id', FIXTURES)
def test_fixture_renders_byte_identical(fixture_id: str, tmp_path: Path) -> None:
    """Render the fixture and assert every produced file matches the fixture snapshot."""
    out = tmp_path / 'render'
    render(FIXTURES_DIR / fixture_id / 'agentorg.json', out)

    fixture_out = FIXTURES_DIR / fixture_id / 'output'
    mismatches: list[str] = []
    missing: list[str] = []
    for src in out.rglob('*'):
        if not src.is_file():
            continue
        rel = src.relative_to(out).as_posix()
        target = fixture_out / rel
        if not target.exists():
            missing.append(rel)
            continue
        if src.read_bytes() != target.read_bytes():
            mismatches.append(rel)
    assert not missing, f'Rendered files missing from fixture {fixture_id!r}: {missing}'
    assert not mismatches, (
        f'Rendered files differ from fixture {fixture_id!r}: {mismatches}\n'
        f'Run `agentorg-render tests/fixtures/{fixture_id}/agentorg.json --out tests/fixtures/{fixture_id}/output` '
        f'to refresh.'
    )
