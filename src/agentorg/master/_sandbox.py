"""Subprocess sandbox that validates user-emitted tool code before it lands in the spec."""

import ast
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SANDBOX_TIMEOUT_SECONDS = 10
SUBPROCESS_PROGRAM = (
    'import importlib.util, asyncio, json, os, sys\n'
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
    "    env_overrides = case.get('env', {}) or {}\n"
    "    env_drop = list(case.get('drop_env', []) or [])\n"
    '    saved = {k: os.environ.get(k) for k in list(env_overrides.keys()) + env_drop}\n'
    '    try:\n'
    '        for k, v in env_overrides.items():\n'
    '            os.environ[k] = v\n'
    '        for k in env_drop:\n'
    '            os.environ.pop(k, None)\n'
    "        raises = case.get('expected_raises')\n"
    '        if raises is not None:\n'
    '            try:\n'
    "                asyncio.new_event_loop().run_until_complete(fn(**case.get('input', {})))\n"
    "            except BaseException as exc:\n"
    '                if raises not in str(exc) and raises != type(exc).__name__:\n'
    '                    raise AssertionError(\n'
    "                        f'test case {i}: expected raise containing {raises!r}, '\n"
    "                        f'got {type(exc).__name__}: {exc}'\n"
    '                    )\n'
    '            else:\n'
    '                raise AssertionError(\n'
    "                    f'test case {i}: expected the function to raise {raises!r}, '\n"
    "                    'but it returned normally'\n"
    '                )\n'
    '            continue\n'
    "        result = asyncio.new_event_loop().run_until_complete(fn(**case.get('input', {})))\n"
    '        rendered = str(result)\n'
    "        contains = case.get('expected_contains')\n"
    '        if contains is not None and contains not in rendered:\n'
    "            raise AssertionError(f'test case {i}: expected output to contain {contains!r}, got {rendered!r}')\n"
    "        equals = case.get('expected_equals')\n"
    '        if equals is not None and rendered != equals:\n'
    "            raise AssertionError(f'test case {i}: expected output {equals!r}, got {rendered!r}')\n"
    '    finally:\n'
    '        for k, v in saved.items():\n'
    '            if v is None:\n'
    '                os.environ.pop(k, None)\n'
    '            else:\n'
    '                os.environ[k] = v\n'
)


class ToolValidationError(Exception):
    """Raised when emitted tool source fails the sandbox validator."""


def _body_is_effectively_empty(body: list[ast.stmt]) -> bool:
    """True when the function body is just `pass`, `...`, or a single docstring/constant expression."""
    real = [n for n in body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    if not real:
        return True  # docstring-only or string-literal-only
    return len(real) == 1 and isinstance(real[0], ast.Pass)


def _find_placeholder_violations(func: ast.AsyncFunctionDef) -> list[str]:
    """Walk `func`'s body and return human-readable descriptions of any placeholder slop found."""
    markers = (
        'TODO',
        'FIXME',
        'placeholder',
        'stub',
        'fake',
        'your code here',
        'add your',
        'in a real',
        'generated code',
        'coming soon',
        'not implemented',
    )
    placeholder_re = re.compile(r'\b(' + '|'.join(re.escape(m) for m in markers) + r')\b', re.IGNORECASE)
    violations: list[str] = []
    if _body_is_effectively_empty(func.body):
        violations.append(f"line {func.lineno}: body is empty/pass-only/docstring-only - write a real implementation")

    for node in ast.walk(func):
        if isinstance(node, ast.Raise):
            raised = node.exc
            target = raised.func if isinstance(raised, ast.Call) else raised
            name = getattr(target, 'id', None) or getattr(target, 'attr', None)
            if name == 'NotImplementedError':
                violations.append(
                    f'line {node.lineno}: `raise NotImplementedError(...)` is not a valid tool body. '
                    'Either write a real call, or use add_or_update_setup_step + a test case with '
                    "`expected_raises='YOUR_ENV_VAR'` to defer credentials to setup-debt.",
                )
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            match = placeholder_re.search(node.value)
            if match:
                snippet = node.value.strip().replace('\n', ' ')[:60]
                violations.append(
                    f'line {node.lineno}: string literal contains placeholder marker '
                    f'{match.group(0)!r} - {snippet!r}',
                )
    return violations


def validate_tool_source(name: str, source: str, test_cases: list[dict] | None = None) -> None:
    """Validate a custom tool's source code before registering it.

    Validation runs in four steps. First, the source is parsed as Python and checked for a
    top-level `async def <name>(...)`. Second, the function body is scanned for placeholder
    patterns (empty/pass-only bodies, `raise NotImplementedError`, string literals containing
    'TODO', 'placeholder', 'in a real scenario', etc.) - any hit rejects the tool. Third, at
    least one entry in `test_cases` is required and the source is imported in a subprocess
    sandbox with a hard timeout. Fourth, each test case is awaited against the imported function.

    A test case is a dict with one of these shapes:
        {'input': {kwargs}, 'expected_contains': 'substring'}          # real call returns text
        {'input': {kwargs}, 'expected_equals': 'exact string'}         # real call exact match
        {'input': {kwargs}, 'expected_raises': 'STRIPE_SECRET_KEY'}    # asserts the function
                                                                       # raises with the
                                                                       # substring in the error
                                                                       # (typical setup-debt
                                                                       # path: prove the env
                                                                       # var is actually read)
    A test case may also supply:
        'env':       {'KEY': 'value', ...}   # set env vars for this case only
        'drop_env':  ['KEY', ...]            # remove env vars for this case only

    Arguments:
        name: The expected top-level async-function name.
        source: Python source code to validate.
        test_cases: Required non-empty list of smoke-test cases. Pass at least one.

    Raises:
        ToolValidationError: If the source fails any validation step.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        msg = f'syntax error: {exc.msg} at line {exc.lineno}'
        raise ToolValidationError(msg) from exc

    async_defs = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)]
    target_fn = next((d for d in async_defs if d.name == name), None)
    if target_fn is None:
        msg = f'no top-level `async def {name}(...)` found in the source'
        raise ToolValidationError(msg)

    violations = _find_placeholder_violations(target_fn)
    if violations:
        msg = 'placeholder-body rejected:\n  - ' + '\n  - '.join(violations)
        raise ToolValidationError(msg)

    if not test_cases:
        msg = (
            f"emit_custom_tool requires at least one test case for '{name}' - pass test_cases=[...] with "
            "an entry shaped {input, expected_contains | expected_equals | expected_raises}. "
            "For credential-bearing tools, use expected_raises='YOUR_ENV_VAR' to prove the env-var read happens."
        )
        raise ToolValidationError(msg)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
        tmp.write(source)
        tmp_path = Path(tmp.name)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as cases_tmp:
        json.dump(list(test_cases), cases_tmp)
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


def validate_skill_source(name: str, skill_md: str) -> None:
    r"""Validate a custom skill's SKILL.md before registering it.

    agno's `LocalSkills` loader requires the file to START with a YAML frontmatter
    block delimited by `---` lines, carrying at minimum a `name` and a `description`.
    The body after the frontmatter is the skill's instructions in markdown.

    Example of a valid SKILL.md:

        ---
        name: negotiation-playbook
        description: Steps for negotiating with a counterparty.
        ---

        # Negotiation playbook

        1. Open with the high anchor.
        2. ...

    Validation checks:
      - `name` matches the lowercase-with-hyphens pattern (folder-name shape).
      - The body starts with `---\n` (YAML frontmatter delimiter).
      - There IS a closing `---\n` for the frontmatter.
      - The frontmatter contains both a `name:` and a `description:` line.
      - There is at least one non-empty line of content after the frontmatter.

    Arguments:
        name: Folder name for the skill (lowercase-with-hyphens).
        skill_md: Full markdown body of the SKILL.md file.

    Raises:
        SkillValidationError: If the name or markdown fails validation.
    """
    import re  # noqa: PLC0415  (stdlib import isolated to this validator)

    if not re.match(r'^[a-z][a-z0-9-]*$', name):
        msg = f"skill name {name!r} must be lowercase-with-hyphens (e.g. 'negotiation-playbook')"
        raise SkillValidationError(msg)

    stripped = skill_md.lstrip()
    if not stripped.startswith('---'):
        msg = (
            'SKILL.md must start with a YAML frontmatter block delimited by `---`. '
            'Example:\n\n---\nname: my-skill\ndescription: One-line summary.\n---\n\n'
            '# My skill\n\n...body...'
        )
        raise SkillValidationError(msg)

    # Split off the frontmatter: lines until the second `---`.
    lines = stripped.splitlines()
    # `lines[0]` is the opening `---`. Find the next standalone `---`.
    closing_idx = None
    for i, ln in enumerate(lines[1:], start=1):
        if ln.strip() == '---':
            closing_idx = i
            break
    if closing_idx is None:
        msg = 'SKILL.md frontmatter is not closed - add a `---` line after the metadata.'
        raise SkillValidationError(msg)

    frontmatter_lines = lines[1:closing_idx]
    frontmatter_text = '\n'.join(frontmatter_lines).lower()
    if 'name:' not in frontmatter_text:
        msg = 'SKILL.md frontmatter must declare a `name:` field.'
        raise SkillValidationError(msg)
    if 'description:' not in frontmatter_text:
        msg = 'SKILL.md frontmatter must declare a `description:` field.'
        raise SkillValidationError(msg)

    body_lines = lines[closing_idx + 1 :]
    if not any(ln.strip() for ln in body_lines):
        msg = 'SKILL.md must contain at least one non-empty line of content after the frontmatter.'
        raise SkillValidationError(msg)
