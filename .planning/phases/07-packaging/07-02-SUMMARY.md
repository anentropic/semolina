---
phase: 07-packaging
plan: 02
subsystem: packaging
tags: [installation-testing, venv-isolation, extras-verification, editable-install]
dependency_graph:
  requires: [verified-wheel, pyproject.toml-extras]
  provides: [installation-validation, extras-validation, dev-workflow-validation]
  affects: [user-installation-experience]
tech_stack:
  added: []
  patterns: [isolated-venv-testing, pip-extras-mechanism, editable-development-install]
key_files:
  created:
    - .planning/phases/07-packaging/install-test-core.txt
    - .planning/phases/07-packaging/install-test-extras.txt
    - .planning/phases/07-packaging/install-test-editable.txt
  modified: []
decisions:
  - Core zero-dependency install validated in isolated venv
  - Optional extras (snowflake, databricks) install only required drivers
  - Combined extras install both backend libraries without conflicts
  - Editable install points to source directory for immediate code reflection
metrics:
  duration_min: 3.83
  completed_date: 2026-02-16
  tasks_completed: 3
  files_created: 3
  commits: 3
---

# Phase 07 Plan 02: Test Installation Scenarios Summary

**One-liner:** Validated all installation scenarios (core, extras, editable) in isolated environments confirming zero-dependency core, correct extras isolation, and development workflow.

## What Was Done

Successfully tested all cubano installation scenarios to verify packaging configuration:

1. **Core installation** - Verified zero-dependency install works in isolated venv
2. **Optional extras** - Tested snowflake, databricks, and combined extras with driver isolation
3. **Editable installation** - Validated development workflow with immediate source code reflection

## Key Outcomes

### Core Installation (PKG-01)
**Environment:** `/tmp/test-core`
- ✅ Zero dependencies: `Requires:` field is empty
- ✅ All public API imports work: `Query, SemanticView, Metric, Dimension, Fact, Q, register, get_engine, unregister, Row`
- ✅ Engine module imports: `Engine, MockEngine`
- ✅ MockEngine instantiation works without backend drivers
- ✅ No snowflake or databricks libraries installed
- **Size:** 1 package installed (cubano only)

### Snowflake Extra (PKG-02)
**Environment:** `/tmp/test-snowflake`
- ✅ `pip install cubano[snowflake]` installs 26 packages
- ✅ `snowflake-connector-python==4.3.0` installed
- ✅ `databricks-sql-connector` NOT installed (isolation verified)
- ✅ `from cubano.engines import SnowflakeEngine` works
- ✅ SnowflakeEngine instantiation succeeds (lazy import, no connection)

### Databricks Extra (PKG-03)
**Environment:** `/tmp/test-databricks`
- ✅ `pip install cubano[databricks]` installs 21 packages
- ✅ `databricks-sql-connector==4.2.5` installed
- ✅ `pyarrow==23.0.0` installed (required by databricks extra)
- ✅ `snowflake-connector-python` NOT installed (isolation verified)
- ✅ `from cubano.engines import DatabricksEngine` works

### Combined Extras
**Environment:** `/tmp/test-combined`
- ✅ `pip install cubano[snowflake,databricks]` installs 37 packages
- ✅ Both `snowflake-connector-python==4.3.0` and `databricks-sql-connector==4.2.5` installed
- ✅ No dependency conflicts
- ✅ Both engines importable: `from cubano.engines import SnowflakeEngine, DatabricksEngine`

### Editable Installation (Development Workflow)
**Environment:** `/tmp/test-editable`
- ✅ `pip install -e .[snowflake,databricks,dev]` installs 41 packages
- ✅ Import points to source: `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/__init__.py`
- ✅ NOT site-packages (immediate source code reflection confirmed)
- ✅ All backend engines importable
- ✅ Dev dependencies installed: `pytest==9.0.2`
- ✅ Quality gates tools available via uv run:
  - `basedpyright 1.38.0`
  - `ruff 0.15.1`
  - `pytest 9.0.2`

## Deviations from Plan

None - plan executed exactly as written.

## Verification Checklist

- [x] Core install has zero dependencies (pip show shows empty Requires)
- [x] Core install can import all public API (Query, SemanticView, fields, Q, registry functions, Row)
- [x] Snowflake extra installs only snowflake-connector-python
- [x] Databricks extra installs only databricks-sql-connector with pyarrow
- [x] Combined extras install both backend libraries
- [x] Editable install points to source directory
- [x] MockEngine works in core-only install

## Files Modified

### Created
- `.planning/phases/07-packaging/install-test-core.txt` - Core installation test results (50 lines)
- `.planning/phases/07-packaging/install-test-extras.txt` - Optional extras test results (100 lines)
- `.planning/phases/07-packaging/install-test-editable.txt` - Editable install test results (72 lines)

## Decisions Made

1. **Core zero-dependency validated** - Confirmed cubano core can be installed with zero runtime dependencies, enabling minimal footprint deployments
2. **Extras isolation verified** - Each extra installs only its required backend driver, preventing unnecessary bloat
3. **Combined extras work** - Multiple extras can be combined without conflicts (37 packages total for full install)
4. **Editable install workflow** - Development install correctly points to source directory for immediate code reflection

## Commits

- `0d12692`: test(07-02): verify core installation with zero dependencies
- `d587650`: test(07-02): verify optional extras installation scenarios
- `1c887e3`: test(07-02): verify editable installation for development

## Next Steps

Installation scenarios fully validated. Ready for:
- PyPI publication testing (test.pypi.org first)
- End-user installation documentation
- CI/CD pipeline integration for automated installation testing
- Version bumping and release workflow

## Self-Check: PASSED

All claimed artifacts verified:
- FOUND: .planning/phases/07-packaging/install-test-core.txt
- FOUND: .planning/phases/07-packaging/install-test-extras.txt
- FOUND: .planning/phases/07-packaging/install-test-editable.txt
- FOUND: commit 0d12692
- FOUND: commit d587650
- FOUND: commit 1c887e3
