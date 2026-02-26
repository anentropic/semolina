---
phase: "09"
plan: "04"
subsystem: codegen-cli
tags: [cli, integration-tests, typer, codegen, snowflake, databricks]
dependency_graph:
  requires: [09-01, 09-02, 09-03]
  provides: [codegen-integration-tests, cli-wiring-verification]
  affects: [cli/codegen.py, cli/utils.py, codegen/generator.py, codegen/loader.py]
tech_stack:
  added: []
  patterns:
    - CliRunner-based end-to-end CLI testing (Typer)
    - fixture-model pattern for codegen integration tests
    - typer.echo() for CLI stdout (CliRunner-compatible vs Rich Console)
key_files:
  created:
    - tests/codegen/fixtures/__init__.py
    - tests/codegen/fixtures/simple_models.py
    - tests/codegen/fixtures/multi_models.py
    - tests/codegen/fixtures/no_models.py
    - tests/codegen/test_cli.py
    - tests/codegen/test_utils.py
  modified:
    - src/cubano/cli/codegen.py
    - src/cubano/cli/utils.py
    - src/cubano/codegen/generator.py
    - src/cubano/codegen/loader.py
decisions:
  - Use typer.echo() for SQL stdout output rather than module-level Rich Console — CliRunner redirects sys.stdout at invoke time, not at module import time
  - Use stdlib glob.glob() for absolute path glob patterns — Python 3.14+ Path.cwd().glob() raises NotImplementedError for absolute patterns
  - Field instance docstrings use __dict__.get('__doc__') instead of inspect.getdoc() to avoid emitting Metric/Dimension/Fact class docstrings as per-field comments
  - Strip and join rendered parts with double newline in generator to eliminate triple-newline artifacts from Jinja2 template whitespace
metrics:
  duration_minutes: 6
  completed_date: "2026-02-17"
  tasks_completed: 8
  files_changed: 10
requirements-completed: [CODEGEN-04, CODEGEN-05, CODEGEN-06, CODEGEN-07, CODEGEN-08]
---

# Phase 09 Plan 04: CLI Wiring Integration Tests Summary

End-to-end CLI integration tests verifying the full `cubano codegen` pipeline through Typer's CliRunner, with four auto-fixed bugs discovered during wiring.

## What Was Built

Created fixture model files (`simple_models.py`, `multi_models.py`, `no_models.py`) and comprehensive integration test suites (`test_cli.py`, `test_utils.py`) exercising all 8 CODEGEN requirements through 35 passing tests. Fixed four integration bugs discovered during wiring.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | Create test fixture model files | 8ff5507 | Done |
| 2 | Create tests/codegen/test_cli.py | 25be108 | Done |
| 3 | CODEGEN-05 input validation test | 25be108 | Done |
| 4 | CODEGEN-06 circular relationship design test | 25be108 | Done |
| 5 | Verify resolve_input_paths with test_utils.py | 25be108 | Done |
| 6 | Run full test suite and fix integration issues | 1f91b55 | Done |
| 7 | Run all quality gates | — | Passed |
| 8 | Review CODEGEN requirement coverage | — | All 8 covered |

## Requirement Coverage

| Requirement | Test |
|-------------|------|
| CODEGEN-01 | `TestCLIBasicBehavior::test_help_shows_usage` |
| CODEGEN-02 | `TestSnowflakeOutput::test_metrics_with_agg_wrapping` |
| CODEGEN-03 | `TestDatabricksOutput::test_measure_expression_uses_sum` |
| CODEGEN-04 | `TestMultipleModels::test_generates_multiple_create_statements` |
| CODEGEN-05 | `TestInputValidation::test_invalid_python_syntax_caught_before_output` |
| CODEGEN-06 | `TestCircularRelationshipDesign::test_model_api_prevents_circular_deps_at_definition` |
| CODEGEN-07 | `TestOutputOptions::test_output_to_file`, `TestInputResolution::test_directory_input_scans_py_files` |
| CODEGEN-08 | `TestCommentHandling`, `TestReadability` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CliRunner mix_stderr not supported in Typer 0.24.0**
- **Found during:** Task 2 (test collection)
- **Issue:** `CliRunner(mix_stderr=False)` raises TypeError — this argument was added in a later Typer version
- **Fix:** Removed `mix_stderr=False`; CliRunner captures both stdout and stderr in `result.output` by default
- **Files modified:** `tests/codegen/test_cli.py`
- **Commit:** 1f91b55

**2. [Rule 1 - Bug] Module-level Rich Console bypasses CliRunner stdout redirect**
- **Found during:** Task 6 (first test run)
- **Issue:** `_stdout = Console(file=sys.stdout)` at module level captures sys.stdout reference at import time; CliRunner redirects sys.stdout at invoke time, so SQL output went to captured stdout visible in "Captured stdout call" but not in `result.output`
- **Fix:** Replaced `_stdout.print(combined_sql)` with `typer.echo(combined_sql)` which uses click's echo that properly respects CliRunner's stdout redirect
- **Files modified:** `src/cubano/cli/codegen.py`
- **Commit:** 1f91b55

**3. [Rule 1 - Bug] Absolute path glob patterns fail in Python 3.14+**
- **Found during:** Task 6 (`test_glob_pattern_matches_files`)
- **Issue:** `Path.cwd().glob("/absolute/path/*.py")` raises `NotImplementedError: Non-relative patterns are unsupported` in Python 3.14; also `*.py` glob suffix caused pattern to be misidentified as explicit file path
- **Fix:** Added glob-char detection (`*`, `?`, `[`) before the `.py` suffix check; replaced `Path.cwd().glob()` with `stdlib.glob.glob()` which handles absolute patterns on all platforms
- **Files modified:** `src/cubano/cli/utils.py`
- **Commit:** 1f91b55

**4. [Rule 1 - Bug] Field class docstrings emitted as per-field comments**
- **Found during:** Task 6 (`test_no_double_blank_lines`)
- **Issue:** `inspect.getdoc(field_obj)` on `Metric()`, `Dimension()`, `Fact()` instances returns the class-level docstring (not instance-level); these verbose multi-line docs were emitted as SQL comments for each field, causing triple-newline violations
- **Fix:** Changed to `field_obj.__dict__.get("__doc__", "") or ""` which only returns explicitly-set instance docstrings; also fixed generator to strip and join parts with double newline to eliminate Jinja2 template whitespace artifacts
- **Files modified:** `src/cubano/codegen/loader.py`, `src/cubano/codegen/generator.py`
- **Commit:** 1f91b55

## Quality Gates

- basedpyright: 0 errors on changed files (pre-existing 42 errors in warehouse engine files unrelated to this plan)
- ruff check: All checks passed on changed files (pre-existing errors in dbt-jaffle-shop workspace)
- ruff format: All changed files formatted
- pytest tests/codegen/: 35 passed, 0 failed
- pytest tests/ -q: 339 passed, 22 failed (all failures pre-existing, warehouse engine tests requiring optional drivers)

## Self-Check: PASSED

Files created/modified verified to exist.
