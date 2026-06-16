"""Subprocess sandbox that validates user-emitted tool code before it lands in the spec."""

import ast
import subprocess
import sys
import tempfile
from pathlib import Path

SANDBOX_TIMEOUT_SECONDS = 10
SUBPROCESS_PROGRAM = (
    'import importlib.util, asyncio, sys\n'
    'path, name = sys.argv[1], sys.argv[2]\n'
    "spec = importlib.util.spec_from_file_location('candidate_tool', path)\n"
    'module = importlib.util.module_from_spec(spec)\n'
    'spec.loader.exec_module(module)\n'
    'fn = getattr(module, name, None)\n'
    "assert callable(fn), 'no callable named ' + name\n"
    "assert asyncio.iscoroutinefunction(fn), name + ' must be async'\n"
)


class ToolValidationError(Exception):
    """Raised when emitted tool source fails the sandbox validator."""


def validate_tool_source(name: str, source: str) -> None:
    """Validate a custom tool's source code before registering it.

    Validation runs in two steps. First, the source is parsed as Python and checked for a top-level
    `async def <name>(...)` function. Second, a fresh subprocess imports the source as a module with
    a hard timeout; any import-time error (syntax issue caught late, missing symbol, banned global
    side effect) propagates as a `ToolValidationError`.

    Arguments:
        name: The expected top-level async-function name.
        source: Python source code to validate.

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
    try:
        result = subprocess.run(
            [sys.executable, '-c', SUBPROCESS_PROGRAM, str(tmp_path), name],
            capture_output=True,
            timeout=SANDBOX_TIMEOUT_SECONDS,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        msg = f'sandbox import exceeded {SANDBOX_TIMEOUT_SECONDS}s timeout'
        raise ToolValidationError(msg) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        msg = f'sandbox import failed:\n{result.stderr.strip()}'
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
