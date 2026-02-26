---
phase: 08-integration-testing
plan: "06"
subsystem: testing
tags: [credentials, unit-tests, env-file, pydantic-settings]
dependency_graph:
  requires: ["08-05"]
  provides: ["tests/test_credentials.py"]
  affects: ["src/cubano/testing/credentials.py"]
tech_stack:
  added: []
  patterns: ["pytest tmp_path fixture", "monkeypatch for env var isolation"]
key_files:
  created: ["tests/test_credentials.py"]
  modified: ["pyproject.toml"]
decisions:
  - "Tests use monkeypatch.chdir() to control working directory for default .env discovery"
  - "Isolate SNOWFLAKE_*/DATABRICKS_* env vars per test to prevent cross-test pollution"
  - "Added 'unit' pytest marker to pyproject.toml to categorize these fast unit tests"
metrics:
  duration_seconds: 118
  completed: "2026-02-17"
  tasks_completed: 1
  files_created: 1
  files_modified: 1
requirements-completed: [INT-06]
---

# Phase 8 Plan 06: Custom env_file Tests Summary

Unit test suite verifying custom .env file path support in SnowflakeCredentials and DatabricksCredentials, covering all three priority-chain tiers with 7 isolated pytest unit tests.

## What Was Built

`tests/test_credentials.py` — 7 unit tests exercising the `CUBANO_ENV_FILE` > `env_file` parameter > default `.env` priority chain for both credential classes.

### Tests Created

| Test | Credential Class | Pattern Tested |
|------|-----------------|----------------|
| `test_snowflake_default_env_file` | SnowflakeCredentials | Default .env in cwd |
| `test_snowflake_custom_env_file` | SnowflakeCredentials | env_file parameter |
| `test_cubano_env_file_priority` | SnowflakeCredentials | CUBANO_ENV_FILE overrides env_file param |
| `test_cubano_env_file_missing_raises_error` | SnowflakeCredentials | CredentialError when CUBANO_ENV_FILE missing |
| `test_databricks_custom_env_file` | DatabricksCredentials | env_file parameter |
| `test_databricks_cubano_env_file_priority` | DatabricksCredentials | CUBANO_ENV_FILE overrides env_file param |
| `test_backward_compatibility` | SnowflakeCredentials | Env vars still work without env_file |

### Key Test Design Decisions

- Used `pytest.MonkeyPatch` to isolate all `SNOWFLAKE_*`, `DATABRICKS_*`, and `CUBANO_ENV_FILE` env vars per test
- Used `monkeypatch.chdir(tmp_path)` to control working directory for default `.env` discovery
- Used `pytest.tmp_path` fixture for automatic temp directory creation and cleanup
- All tests marked `@pytest.mark.unit` — run in 0.03s with no warehouse connections

## Quality Gate Results

```
uv run pytest tests/test_credentials.py -v
  7 passed in 0.03s

uv run basedpyright tests/test_credentials.py
  0 errors, 0 warnings, 0 notes

uv run ruff check tests/test_credentials.py
  All checks passed!
```

### Code Coverage

```
Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
src/cubano/testing/credentials.py      48     20    58%   106-112, 183-203
```

Uncovered lines (106-112, 183-203) are the config file fallback paths (`.cubano.toml`, `~/.config/cubano/config.toml`) — out of scope for this plan, not exercised by env_file tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Config] Added 'unit' pytest marker to pyproject.toml**
- **Found during:** Task 1
- **Issue:** `@pytest.mark.unit` used in tests but marker not registered in `[tool.pytest.ini_options]`
- **Fix:** Added `"unit: Pure unit tests with no external dependencies"` to markers list
- **Files modified:** `pyproject.toml`
- **Commit:** 014935a (same commit)

## Commits

| Commit | Message | Files |
|--------|---------|-------|
| 014935a | feat(08-06): add unit tests for custom env_file parameter and CUBANO_ENV_FILE priority | tests/test_credentials.py, pyproject.toml |

## Running the Tests

```bash
# Run all credential unit tests
uv run pytest tests/test_credentials.py -v

# Run with coverage
uv run pytest tests/test_credentials.py --cov=cubano.testing.credentials --cov-report=term-missing

# Run just the priority chain test
uv run pytest tests/test_credentials.py::test_cubano_env_file_priority -v

# Run all unit-marked tests across the suite
uv run pytest -m unit -v
```

## Self-Check: PASSED

- tests/test_credentials.py: FOUND
- pyproject.toml: FOUND (unit marker added)
- commit 014935a: FOUND
- All 7 tests pass
- Type checking: 0 errors
- Linting: All checks passed
