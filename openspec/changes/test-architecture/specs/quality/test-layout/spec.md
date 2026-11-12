# Spec Delta

## Purpose

Keeps the test tree a one-to-one mirror of the source tree, so every module has an obvious home for its tests and
untested modules are visible. This holds for the agentorg library and for every project it renders.

## ADDED Requirements

### Requirement: Source modules map to mirrored test files
For each source module `src/<pkg>/<path>/<name>.py` or `src/<pkg>/<path>/_<name>.py`, the tests SHALL live in
`tests/<path>/test_<name>.py`. One test file SHALL cover exactly one source module.

#### Scenario: Private module mirrored
- **WHEN** the source tree contains `src/agentorg/core/operations/_scheduler.py`
- **THEN** its tests are in `tests/core/operations/test_scheduler.py`

#### Scenario: Public and private twin rejected
- **WHEN** both `_scheduler.py` and `scheduler.py` exist in the same package
- **THEN** the layout check fails because the test path is ambiguous

### Requirement: Missing and orphan test files fail the gate
The layout check SHALL run as part of `nox -s checks`. It SHALL fail in two cases:
- a source module has no mirrored test file and is not exempt;
- a `test_*.py` file outside `tests/e2e/` has no matching source module.

The failure message SHALL list every offending path.

#### Scenario: New module without tests
- **WHEN** a contributor adds `src/agentorg/core/operations/_bus.py` without `tests/core/operations/test_bus.py`
- **THEN** `nox -s checks` fails naming both paths

#### Scenario: Orphan test after a move
- **WHEN** a source module is renamed but its test file is not
- **THEN** the check fails naming the orphan test file

### Requirement: Exemptions are declared explicitly
Some paths SHALL be exempt from the mirror rule without being declared:
- `__init__.py` modules that only re-export names;
- `conftest.py`, `__init__.py` and fixture data under `tests/`;
- template sources under `src/agentorg/core/render/templates/`, which are covered by render tests;
- `tests/e2e/`.

Any other exemption SHALL be listed in `[tool.agentorg.test-layout] exempt` in `pyproject.toml`, and each listed path SHALL
exist.

#### Scenario: Base-class module exempt
- **WHEN** `src/agentorg/core/spec/_config.py` is listed under `exempt`
- **THEN** the check passes without `tests/core/spec/test_config.py`

#### Scenario: Stale exemption
- **WHEN** an exempt entry names a path that no longer exists
- **THEN** the check fails naming the stale entry

#### Scenario: Logic in an init module
- **WHEN** an `__init__.py` defines a function rather than only re-exporting
- **THEN** it is not exempt by default and needs a mirrored test file

### Requirement: Rendered projects follow the same rule
Every project rendered by agentorg SHALL have tests mirroring its own `src/` tree. Its `nox -s checks` SHALL run the same
layout check.

#### Scenario: Rendered routes test location
- **WHEN** a project is rendered from the full template
- **THEN** the tests for `src/<package>/app/routes.py` are in `tests/app/test_routes.py`

#### Scenario: Rendered gate enforces layout
- **WHEN** a user adds a module to a rendered project without a mirrored test
- **THEN** the rendered project's `nox -s checks` fails
