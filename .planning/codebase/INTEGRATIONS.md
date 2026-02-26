# External Integrations

**Analysis Date:** 2026-02-17

## Data Warehouses

Cubano is a query library that integrates with two data warehouses via optional connector packages. Both use lazy imports — the driver is only loaded when the engine class is instantiated, so users without a warehouse installed get a clear ImportError with install instructions.

**Snowflake:**
- Purpose: Execute queries against Snowflake semantic views using `AGG()` syntax
- SDK/Client: `snowflake-connector-python>=4.3.0` (optional extra `cubano[snowflake]`)
- Engine: `src/cubano/engines/snowflake.py` - `SnowflakeEngine`
- SQL dialect: `src/cubano/engines/sql.py` - `SnowflakeDialect`
  - Identifier quoting: double quotes (`"column"`)
  - Metric wrapping: `AGG("metric_name")`
  - Grouping: `GROUP BY ALL`
- Connection: per-`execute()` call, no pooling
- Auth: username/password or `authenticator` parameter

**Databricks:**
- Purpose: Execute queries against Databricks metric views using `MEASURE()` syntax
- SDK/Client: `databricks-sql-connector[pyarrow]>=4.2.5` (optional extra `cubano[databricks]`)
- Engine: `src/cubano/engines/databricks.py` - `DatabricksEngine`
- SQL dialect: `src/cubano/engines/sql.py` - `DatabricksDialect`
  - Identifier quoting: backticks (`` `column` ``)
  - Metric wrapping: `MEASURE(\`metric_name\`)`
  - Grouping: `GROUP BY ALL` (requires Databricks Runtime 12.2 LTS+)
  - Unity Catalog: three-part names (`catalog.schema.view`) supported transparently
- Connection: per-`execute()` call, no pooling
- Auth: personal access token (`access_token`)

## Credential Configuration

Credentials are loaded via a fallback chain implemented in `src/cubano/testing/credentials.py` (dev/test use only — not a runtime dependency).

**Snowflake credential sources (priority order):**
1. Environment variables with `SNOWFLAKE_` prefix:
   - `SNOWFLAKE_ACCOUNT` - Account identifier (e.g., `xy12345.us-east-1`)
   - `SNOWFLAKE_USER` - Username
   - `SNOWFLAKE_PASSWORD` - Password (stored as `SecretStr`)
   - `SNOWFLAKE_WAREHOUSE` - Warehouse name
   - `SNOWFLAKE_DATABASE` - Database name
   - `SNOWFLAKE_ROLE` - Role (optional)
2. `.env` file in project root (path overridable via `CUBANO_ENV_FILE` env var)
3. `.cubano.toml` config file in project root (`[snowflake]` section)
4. `~/.config/cubano/config.toml` (`[snowflake]` section)

**Databricks credential sources (priority order):**
1. Environment variables with `DATABRICKS_` prefix:
   - `DATABRICKS_SERVER_HOSTNAME` - Workspace hostname
   - `DATABRICKS_HTTP_PATH` - SQL warehouse path (e.g., `/sql/1.0/warehouses/{id}`)
   - `DATABRICKS_ACCESS_TOKEN` - Personal access token (stored as `SecretStr`)
   - `DATABRICKS_CATALOG` - Default catalog (optional, defaults to `main`)
2. `.env` file in project root (path overridable via `CUBANO_ENV_FILE` env var)
3. `.cubano.toml` config file in project root (`[databricks]` section)
4. `~/.config/cubano/config.toml` (`[databricks]` section)

**Note:** `pydantic-settings` (used for credential loading) is a **dev dependency only** — it is NOT listed in `[project.dependencies]`. Production users pass connection params directly to engine constructors.

## File Storage

- Local filesystem only
- Codegen CLI writes SQL/YAML output to stdout or a user-specified file path (`--output`)

## Authentication & Identity

- No built-in auth provider — authentication is delegated to warehouse connectors
- Snowflake: username/password or `authenticator` parameter (e.g., SSO, OAuth)
- Databricks: personal access token

## Monitoring & Observability

**Error Tracking:**
- None (library — errors propagate as exceptions to caller)

**Logs:**
- `rich.console.Console` for CLI output (stdout/stderr)
- Errors translated to `RuntimeError` with human-readable messages including warehouse error codes

## CI/CD & Deployment

**Hosting:**
- PyPI (library distribution)
- Documentation: GitHub Pages at `https://anentropic.github.io/cubano/`

**CI Pipeline:**
- GitHub Actions - `.github/workflows/ci.yml`
  - Jobs: typecheck (basedpyright), lint (ruff check), format (ruff format), test (pytest)
  - Matrix: Python 3.11 and 3.14
  - Snowflake secrets injected as env vars for warehouse integration tests
  - Uses `astral-sh/setup-uv@v7` with lockfile caching
- Docs workflow: `.github/workflows/docs.yml`
- PR workflow: `.github/workflows/pr.yml`
- Release workflow: `.github/workflows/release.yml`
  - Changelog generation: `.cliff.toml` (git-cliff)

## Webhooks & Callbacks

**Incoming:** None

**Outgoing:** None

## Code Generation Output Targets

The `cubano codegen` CLI generates warehouse-native DDL from Python model definitions:

**Snowflake:**
- Template: `src/cubano/codegen/templates/snowflake.sql.jinja2`
- Output: SQL `CREATE SEMANTIC VIEW` statements

**Databricks:**
- Template: `src/cubano/codegen/templates/databricks.yaml.jinja2`
- Output: YAML metric view definitions

---

*Integration audit: 2026-02-17*
