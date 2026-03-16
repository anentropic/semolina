# Research Summary: Semolina v0.3 Arrow & Connection Layer

**Domain:** ADBC connection pools, Arrow-native cursors, TOML configuration
**Researched:** 2026-03-16
**Overall confidence:** HIGH

## Executive Summary

v0.3 replaces Semolina's hand-rolled Engine ABC (SnowflakeEngine, DatabricksEngine, MockEngine) with [adbc-poolhouse](https://pypi.org/project/adbc-poolhouse/) connection pools and evolves `.execute()` from returning eagerly-materialized `Result` objects to returning a `SemolinaCursor` with Arrow-native fetch methods.

**adbc-poolhouse** is a published PyPI package (docs: https://anentropic.github.io/adbc-poolhouse/) that provides:
- `create_pool(config)` / `close_pool(pool)` / `managed_pool(config)` — pool lifecycle
- `pool.connect()` context manager — connection checkout
- Typed pydantic-settings config classes per backend: `SnowflakeConfig`, `DatabricksConfig`, etc.
- SQLAlchemy QueuePool under the hood (pool_size, max_overflow, timeout, recycle)
- 12 backend configs with env var prefixes (`SNOWFLAKE_`, `DATABRICKS_`, etc.)
- SecretStr for sensitive fields (password, token, private_key_pem)

The ADBC DBAPI cursor provides both standard PEP 249 methods (fetchone, fetchall, fetchmany) and Arrow extensions (fetch_arrow_table, fetch_record_batch_reader). SemolinaCursor wraps this with Row convenience methods on top.

## Key Findings

**Stack additions:**
- `adbc-poolhouse` — core dependency (brings SQLAlchemy QueuePool, ADBC driver management)
- `adbc-poolhouse[snowflake]` — Snowflake extra (brings adbc-driver-snowflake + pyarrow)
- `adbc-poolhouse[databricks]` — Databricks extra (Foundry-distributed driver, not PyPI)
- `pydantic-settings` — already used by adbc-poolhouse configs; may need for TomlSettingsSource
- `pyarrow` — transitive via ADBC drivers; needed explicitly for MockPool and SemolinaCursor

**Architecture:** Pool instances (from adbc-poolhouse) replace Engine classes in registry. Registry stores `(pool, dialect)` tuples. SemolinaCursor wraps ADBC cursor. SQL generation (Dialect + build_select_with_params) is unchanged.

**Snowflake auth methods** (via adbc-poolhouse SnowflakeConfig): password, JWT private key (file or PEM), OAuth token, external browser SSO.

**Databricks auth** (via adbc-poolhouse DatabricksConfig): PAT token, URI mode, or individual fields (host + http_path + token). Foundry-distributed driver required.

## Critical Pitfalls

1. **ADBC Snowflake bind parameter support** — Researchers flagged that the ADBC Snowflake driver may not support parameterized SELECT queries (apache/arrow-adbc#1144). If true, Semolina needs inline parameter rendering with proper escaping as fallback. Must verify early.

2. **Databricks ADBC driver is Foundry-distributed** — Not on PyPI. adbc-poolhouse supports it but the driver install is separate. This is a packaging/docs concern, not a blocker.

3. **Arrow type normalization** — ADBC returns Arrow types (Decimal128, timestamps). SemolinaCursor's Row conversion path must normalize these to Python natives or snapshots/equality break.

4. **Cursor lifecycle with RecordBatchReader** — Cursor must remain alive while streaming. SemolinaCursor context manager must handle this.

5. **Breaking API change** — `.execute()` returns SemolinaCursor instead of Result. 759 tests and all docs affected. Migration path needed.

## Implications for Roadmap

Suggested phase structure:

1. **Pool Registry + Dialect Enum + MockPool** — Foundation. Replace Engine registry with pool registry. MockPool provides same cursor API with in-memory Arrow data. No external deps beyond pyarrow.

2. **SemolinaCursor + Query Integration** — Core API change. SemolinaCursor wraps ADBC cursor, adds fetchall_rows/fetchmany_rows/fetchone_row. .execute() returns SemolinaCursor. Testable with MockPool.

3. **Real Pool Integration (Snowflake + Databricks)** — Wire adbc-poolhouse create_pool() with SnowflakeConfig/DatabricksConfig. Verify bind param support. Integration tests.

4. **TOML Config + pool_from_config()** — TomlSettingsSource, .semolina.toml with connection sections, pool_from_config() helper. Independent track.

5. **query() Shorthand + Polish** — query(metrics=..., dimensions=...) sugar. API cleanup and deprecation.

## Gaps to Address

- ADBC Snowflake bind parameter support — verify in Phase 3, have fallback plan
- Databricks Foundry driver install story — docs/packaging concern
- Arrow Decimal128 → Python int/float normalization in Row conversion
- MockPool pyarrow requirement — should pyarrow be optional for mock-only usage?
- Go runtime conflict loading both Snowflake + FlightSQL drivers simultaneously

---

*Research completed: 2026-03-16*
*Correction: adbc-poolhouse is a published PyPI package, not project-internal*
