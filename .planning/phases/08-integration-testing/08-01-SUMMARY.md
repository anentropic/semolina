---
phase: 08-integration-testing
plan: 01
subsystem: testing
tags: [credentials, fixtures, pydantic-settings, security]
dependencies:
  requires: []
  provides: [credential-management, session-fixtures]
  affects: [tests/conftest.py]
tech_stack:
  added: [pydantic-settings, pytest-xdist]
  patterns: [fallback-chain, session-scoped-fixtures, secret-masking]
key_files:
  created:
    - src/cubano/testing/__init__.py
    - src/cubano/testing/credentials.py
  modified:
    - pyproject.toml
    - tests/conftest.py
    - uv.lock
decisions: []
metrics:
  duration_minutes: 3.08
  task_count: 3
  file_count: 5
  completed_date: 2026-02-17
requirements-completed: [INT-06]
---

# Phase 08 Plan 01: Smart Credential Management Summary

**One-liner:** JWT-free credential loading with env → .env → config fallback chain using pydantic-settings BaseSettings with SecretStr masking for passwords and tokens.

## What Was Built

Implemented smart credential management for integration tests with automatic environment variable fallback and graceful degradation when credentials are unavailable.

**Core Components:**

1. **Credential Classes** (`src/cubano/testing/credentials.py`):
   - `SnowflakeCredentials` with fields: account, user, password, warehouse, database, role
   - `DatabricksCredentials` with fields: server_hostname, http_path, access_token, catalog
   - Both use pydantic-settings `BaseSettings` for automatic env var and .env file loading
   - `CredentialError` exception with clear guidance on expected variables

2. **Fallback Chain** (3-tier):
   - **Tier 1:** Environment variables (SNOWFLAKE_*, DATABRICKS_*) - automatic via pydantic-settings
   - **Tier 2:** .env file in project root - automatic via pydantic-settings
   - **Tier 3:** Config files (.cubano.toml, ~/.config/cubano/config.toml) - manual via tomllib
   - **Tier 4:** Raise CredentialError with helpful message

3. **Session-Scoped Fixtures** (`tests/conftest.py`):
   - `snowflake_credentials` fixture - loads once per test session
   - `databricks_credentials` fixture - loads once per test session
   - Both use `pytest.skip()` pattern to gracefully skip tests when credentials unavailable

4. **Security:**
   - All password/token fields use `SecretStr` to mask values in logs and repr output
   - No credentials logged in plain text

**Dependencies Added:**
- `pydantic-settings>=2.7.0` - Environment variable management with BaseSettings
- `pytest-xdist>=3.6.0` - Parallel test execution with worker isolation

## Task Breakdown

### Task 1: Add pydantic-settings and pytest-xdist (Commit: e84de9f)

Added two dev dependencies to pyproject.toml in alphabetical order:
- pydantic-settings for credential management with env var fallback
- pytest-xdist for parallel test execution

**Files:** pyproject.toml, uv.lock

### Task 2: Create credential loader (Commit: 5134bce)

Implemented SnowflakeCredentials and DatabricksCredentials classes with:
- pydantic-settings BaseSettings for automatic env/env file loading
- classmethod `load()` implementing 3-tier fallback chain
- tomllib (Python 3.11+) for config file reading
- SecretStr for password/token masking
- CredentialError with clear error messages

**Files:** src/cubano/testing/__init__.py, src/cubano/testing/credentials.py

### Task 3: Add session-scoped fixtures (Commit: a5374a3)

Added two session-scoped pytest fixtures to tests/conftest.py:
- `snowflake_credentials` - calls SnowflakeCredentials.load()
- `databricks_credentials` - calls DatabricksCredentials.load()
- Both use pytest.skip() to gracefully skip tests when CredentialError raised
- Session scope ensures credentials loaded once per test run

**Files:** tests/conftest.py

## Deviations from Plan

None - plan executed exactly as written.

## Usage Examples

### Setting Credentials via Environment Variables

```bash
# Snowflake
export SNOWFLAKE_ACCOUNT=xy12345.us-east-1
export SNOWFLAKE_USER=myuser
export SNOWFLAKE_PASSWORD=mypassword
export SNOWFLAKE_WAREHOUSE=COMPUTE_WH
export SNOWFLAKE_DATABASE=ANALYTICS

# Databricks
export DATABRICKS_SERVER_HOSTNAME=dbc-a1b2c3d4.cloud.databricks.com
export DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/abc123
export DATABRICKS_ACCESS_TOKEN=dapi1234567890abcdef
```

### Setting Credentials via .env File

Create `.env` in project root:

```bash
SNOWFLAKE_ACCOUNT=xy12345.us-east-1
SNOWFLAKE_USER=myuser
SNOWFLAKE_PASSWORD=mypassword
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=ANALYTICS
```

### Using Credentials in Tests

```python
def test_snowflake_query(snowflake_credentials):
    # Test will skip if credentials unavailable
    engine = SnowflakeEngine(snowflake_credentials)
    # ... test logic
```

### Credential Masking

```python
>>> from cubano.testing.credentials import SnowflakeCredentials
>>> creds = SnowflakeCredentials.load()
>>> print(creds.password)
**********
>>> print(repr(creds))
SnowflakeCredentials(account='xy12345.us-east-1', user='myuser', password=SecretStr('**********'), ...)
```

## Verification Results

All verification steps passed:

1. ✅ Environment variable loading works (tested with SNOWFLAKE_* variables)
2. ✅ Credential masking works (password prints as `**********`)
3. ✅ Pytest fixture collection succeeds without credentials (286 tests collected)
4. ✅ Existing tests run successfully (16 tests in test_models.py passed)
5. ✅ Type checking passes (basedpyright 0 errors)
6. ✅ Linting passes (ruff check all passed)

## Quality Gates

- ✅ `uv run basedpyright` - 0 errors, 0 warnings
- ✅ `uv run ruff check` - All checks passed
- ✅ `uv run pytest tests/test_models.py` - 16 passed
- ✅ Dependencies in pyproject.toml

## Next Steps

Plan 08-02 will build on this credential management foundation to create:
- Warehouse connection fixtures using these credentials
- Real Snowflake/Databricks engine fixtures
- Connection pooling and lifecycle management

## Self-Check: PASSED

**Files created:**
- ✅ /Users/paul/Documents/Dev/Personal/cubano/src/cubano/testing/__init__.py
- ✅ /Users/paul/Documents/Dev/Personal/cubano/src/cubano/testing/credentials.py

**Files modified:**
- ✅ /Users/paul/Documents/Dev/Personal/cubano/pyproject.toml
- ✅ /Users/paul/Documents/Dev/Personal/cubano/tests/conftest.py
- ✅ /Users/paul/Documents/Dev/Personal/cubano/uv.lock

**Commits exist:**
- ✅ e84de9f: chore(08-01): add pydantic-settings and pytest-xdist dev dependencies
- ✅ 5134bce: feat(08-01): implement credential loader with fallback chain
- ✅ a5374a3: feat(08-01): add session-scoped credential fixtures to conftest
