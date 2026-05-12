"""End-to-end test: render each fixture and assert byte-identity against the fixture's `output/` snapshot.

`agentorg.core.render` walks the template, renders Jinja files, and copies the rest verbatim. The fixture's `output/`
directory is the golden snapshot; this test diffs every file the renderer produces against it. Run-time artifacts like
`.env` / `uv.lock` / `node_modules/` sit alongside in the fixture as out-of-scope extras.
"""

from pathlib import Path

import pytest

from agentorg.core import render

REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / 'fixtures'
FIXTURES = ['org']


@pytest.mark.parametrize('fixture_id', FIXTURES)
def test_fixture_renders_byte_identical(fixture_id: str, tmp_path: Path) -> None:
    """Render the fixture and assert every produced file matches the fixture snapshot."""
    out = tmp_path / 'render'
    render(FIXTURES_DIR / fixture_id / 'config', out)

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
        f'The fixture is the hand-maintained expected output. If the renderer is wrong, '
        f'fix the template; if the new output is intended, edit the fixture by hand to match.'
    )
