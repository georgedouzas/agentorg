"""Render a fixture's .env from the central tests/fixtures/.env.

Reads keys from `tests/fixtures/<fixture>/output/example.env`, fills values from
`tests/fixtures/.env`, and writes `tests/fixtures/<fixture>/output/.env`.

Usage:
    python tests/fixtures/render_env.py                # all fixtures
    python tests/fixtures/render_env.py investment-team
"""

from __future__ import annotations

import sys
from pathlib import Path

FIXTURES_ROOT = Path(__file__).resolve().parent


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, _, value = stripped.partition('=')
        values[key.strip()] = value.strip()
    return values


def render_fixture_env(name: str, central: dict[str, str]) -> None:
    example = FIXTURES_ROOT / name / 'output' / 'example.env'
    if not example.exists():
        print(f'Skipping {name!r}: {example} not found.', file=sys.stderr)
        return
    out_lines: list[str] = []
    missing: list[str] = []
    for line in example.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            out_lines.append(line)
            continue
        key, _, default = stripped.partition('=')
        key = key.strip()
        value = central.get(key, default.strip())
        if key not in central and not default.strip():
            missing.append(key)
        out_lines.append(f'{key}={value}')
    target = FIXTURES_ROOT / name / 'output' / '.env'
    target.write_text('\n'.join(out_lines) + '\n')
    print(f'Wrote {target}')
    if missing:
        print(f'  Unset in central .env: {", ".join(missing)}', file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    available = sorted(p.name for p in FIXTURES_ROOT.iterdir() if p.is_dir())
    target = args[0] if args else 'all'
    if target != 'all' and target not in available:
        print(f'Unknown fixture {target!r}. Available: {", ".join(available)}.', file=sys.stderr)
        return 2
    central_path = FIXTURES_ROOT / '.env'
    if not central_path.exists():
        print(f'Missing {central_path}. Create it with your secrets first.', file=sys.stderr)
        return 1
    central = _parse_env(central_path)
    targets = available if target == 'all' else [target]
    for name in targets:
        render_fixture_env(name, central)
    return 0


if __name__ == '__main__':
    sys.exit(main())
