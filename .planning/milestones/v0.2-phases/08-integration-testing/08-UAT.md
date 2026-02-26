---
status: diagnosed
phase: 08-integration-testing
source: 08-01-SUMMARY.md, 08-02-SUMMARY.md, 08-03-SUMMARY.md, 08-04-SUMMARY.md
started: 2026-02-17T00:00:00Z
updated: 2026-02-17T00:00:00Z
gap_plans: 08-05-PLAN.md (implement), 08-06-PLAN.md (test)
verification: PASSED (plan checker verified all coverage)
---

## Current Test

[testing complete]

## Tests

### 1. Credential Management — Environment Variable Loading
expected: Snowflake/Databricks credentials load from SNOWFLAKE_* and DATABRICKS_* environment variables. Sensitive fields (password, token) are masked when printed/logged as `**********`.
result: pass

### 2. Credential Management — Fallback Chain
expected: Credentials load from multiple sources: (1) env vars, (2) .env file, (3) config files. If all missing, CredentialError raised with helpful guidance.
result: issue
reported: "we should have an option arg for passing an env file path to override default (.env in cwd)"
severity: major

### 3. Session-Scoped Fixtures
expected: `snowflake_credentials` and `databricks_credentials` fixtures are session-scoped, loading once per test run. Tests skip gracefully when credentials unavailable.
result: pass

### 4. Pytest Markers Registered
expected: `pytest --markers` shows `mock`, `warehouse`, `snowflake`, and `databricks` markers for selective test execution.
result: pass

### 5. Per-Worker Schema Isolation
expected: `test_schema_name` fixture generates unique schema names per pytest-xdist worker: `cubano_test_main` for single worker, `cubano_test_gw0`/`cubano_test_gw1`/etc for parallel workers.
result: pass

### 6. Connection Lifecycle Management
expected: Warehouse connection fixtures create schemas on setup, drop them on teardown (even if tests fail). Finally blocks ensure cleanup happens.
result: pass

### 7. Mock Engine Fixture
expected: `mock_engine` fixture is function-scoped and provides a fresh MockEngine instance per test for fast local testing without warehouse connections.
result: pass

### 8. Mock Test Suite — Field Combinations
expected: Mock tests validate query construction for single metric, multiple metrics, metric+dimension, and dimension-only queries. Tests complete in < 1 second.
result: pass

### 9. Mock Test Suite — Ordering and Limiting
expected: Mock tests validate ORDER BY and LIMIT API usage. Tests execute without errors and validate query construction (not result ordering/limiting).
result: pass

### 10. Mock Fixture Data Quality
expected: Mock fixture data uses realistic types (Decimal for money, datetime for timestamps, bool for flags) and includes edge cases (null values, min/max values).
result: pass

### 11. Integration Tests — Real Warehouse Execution
expected: Integration tests execute real queries against warehouse, validate result structure (schema, types, row count > 0 for data-present views).
result: pass

### 12. Integration Tests — Parallel Safety
expected: Warehouse integration tests run successfully with `pytest -n auto` (parallel execution). Per-worker schema isolation prevents data conflicts between workers.
result: pass

### 13. CI Integration — Marker-Based Execution
expected: CI workflow runs warehouse tests only (via `pytest -m warehouse`), mock tests always run. Secrets for warehouse credentials loaded from GitHub Actions repository secrets.
result: pass

## Summary

total: 13
passed: 12
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Credentials can be loaded from a custom .env file path, not just default .env in cwd"
  status: failed
  reason: "User reported: we should have an option arg for passing an env file path to override default (.env in cwd)"
  severity: major
  test: 2
  root_cause: "SnowflakeCredentials and DatabricksCredentials have hardcoded env_file='.env' in model_config, no override capability"
  artifacts:
    - path: "src/cubano/testing/credentials.py"
      issue: "SettingsConfigDict has hardcoded env_file='.env', pydantic-settings supports _env_file parameter at instantiation but not exposed in .load() method"
  missing:
    - "Add env_file parameter to SnowflakeCredentials.load() and DatabricksCredentials.load()"
    - "Check CUBANO_ENV_FILE environment variable as priority override"
    - "Pass _env_file to BaseSettings instantiation for runtime path control"
  debug_session: ".planning/quick/custom-env-file-path/INVESTIGATION.md"
