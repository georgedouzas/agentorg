"""Subprocess sandbox that validates user-emitted tool code before it lands in the spec."""

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SANDBOX_TIMEOUT_SECONDS = 10
SUBPROCESS_PROGRAM = (
    'import importlib.util, asyncio, json, sys\n'
    'path, name, cases_path = sys.argv[1], sys.argv[2], sys.argv[3]\n'
    "spec = importlib.util.spec_from_file_location('candidate_tool', path)\n"
    'module = importlib.util.module_from_spec(spec)\n'
    'spec.loader.exec_module(module)\n'
    'fn = getattr(module, name, None)\n'
    "assert callable(fn), 'no callable named ' + name\n"
    "assert asyncio.iscoroutinefunction(fn), name + ' must be async'\n"
    'with open(cases_path) as f:\n'
    '    cases = json.load(f)\n'
    'for i, case in enumerate(cases):\n'
    "    result = asyncio.new_event_loop().run_until_complete(fn(**case.get('input', {})))\n"
    '    rendered = str(result)\n'
    "    contains = case.get('expected_contains')\n"
    '    if contains is not None and contains not in rendered:\n'
    "        raise AssertionError(f'test case {i}: expected output to contain {contains!r}, got {rendered!r}')\n"
    "    equals = case.get('expected_equals')\n"
    '    if equals is not None and rendered != equals:\n'
    "        raise AssertionError(f'test case {i}: expected output {equals!r}, got {rendered!r}')\n"
)


class ToolValidationError(Exception):
    """Raised when emitted tool source fails the sandbox validator."""


def validate_tool_source(name: str, source: str, test_cases: list[dict] | None = None) -> None:
    """Validate a custom tool's source code before registering it.

    Validation runs in three steps. First, the source is parsed as Python and checked for a
    top-level `async def <name>(...)` function. Second, a fresh subprocess imports the source
    as a module with a hard timeout. Third (optional), each entry in `test_cases` is awaited
    against the function and the result checked.

    Each test case is a dict:
        {'input': {kwargs}, 'expected_contains': 'substring'}  # OR
        {'input': {kwargs}, 'expected_equals': 'exact string'}

    Arguments:
        name: The expected top-level async-function name.
        source: Python source code to validate.
        test_cases: Optional list of smoke-test cases to run against the imported function.

    Raises:
        ToolValidationError: If the source fails any validation step.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        msg = f'syntax error: {exc.msg} at line {exc.lineno}'
        raise ToolValidationError(msg) from exc

    async_defs = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)]
    if not any(d.name == name for d in async_defs):
        msg = f'no top-level `async def {name}(...)` found in the source'
        raise ToolValidationError(msg)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
        tmp.write(source)
        tmp_path = Path(tmp.name)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as cases_tmp:
        json.dump(list(test_cases or []), cases_tmp)
        cases_tmp_path = Path(cases_tmp.name)
    try:
        result = subprocess.run(
            [sys.executable, '-c', SUBPROCESS_PROGRAM, str(tmp_path), name, str(cases_tmp_path)],
            capture_output=True,
            timeout=SANDBOX_TIMEOUT_SECONDS,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        msg = f'sandbox import or test case exceeded {SANDBOX_TIMEOUT_SECONDS}s timeout'
        raise ToolValidationError(msg) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
        cases_tmp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        msg = f'sandbox check failed:\n{stderr}'
        raise ToolValidationError(msg)


class SkillValidationError(Exception):
    """Raised when emitted skill source fails validation."""


_SKILL_NAME_PATTERN = '^[a-z][a-z0-9-]*$'


def validate_skill_source(name: str, skill_md: str) -> None:
    """Validate a custom skill's SKILL.md before registering it.

    Skills are filesystem-shaped (a folder containing SKILL.md and optional supporting files),
    so they cannot be subprocess-imported like tools. Validation is purely structural here:
    the skill name must be a lowercase-with-hyphens identifier, and the SKILL.md body must
    begin with a markdown H1 heading and contain at least one non-heading line of content.

    Arguments:
        name: Folder name for the skill (lowercase-with-hyphens).
        skill_md: Full markdown body of the SKILL.md file.

    Raises:
        SkillValidationError: If the name or markdown fails validation.
    """
    import re  # noqa: PLC0415  (stdlib import isolated to this validator)

    if not re.match(_SKILL_NAME_PATTERN, name):
        msg = f"skill name {name!r} must be lowercase-with-hyphens (e.g. 'negotiation-playbook')"
        raise SkillValidationError(msg)

    stripped = skill_md.strip()
    if not stripped.startswith('# '):
        msg = 'SKILL.md must start with a level-1 markdown heading (`# Skill name`)'
        raise SkillValidationError(msg)

    non_heading = [line for line in stripped.splitlines()[1:] if line.strip() and not line.startswith('#')]
    if not non_heading:
        msg = 'SKILL.md must contain at least one non-heading line of content'
        raise SkillValidationError(msg)
