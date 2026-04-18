# Gap Report

**Generated:** 2026-04-10
**Source root:** src/
**Language:** python
**Total undocumented symbols:** 17
**Potentially stale pages:** 0

## Undocumented Symbols

### semolina/__init__.py (`__all__`)

- `Predicate` (class) -- base class for filter predicates, used in `.where()` type hints
- `Dialect` (StrEnum) -- enum of supported warehouse dialects (`snowflake`, `databricks`)
- `get_pool` (function) -- retrieve a registered pool+dialect tuple by name
- `get_engine` (function) -- retrieve a registered engine by name (legacy)
- `SemolinaConnectionError` (exception) -- raised on warehouse connection failures
- `SemolinaViewNotFoundError` (exception) -- raised when a semantic view does not exist

### semolina/testing (`__all__`)

- `CredentialError` (exception) -- raised when test credentials are missing
- `SnowflakeCredentials` (class) -- pydantic settings for Snowflake test credentials
- `DatabricksCredentials` (class) -- pydantic settings for Databricks test credentials

### semolina/engines (`__all__`)

- `Engine` (ABC) -- abstract base class for backend engines
- `DialectABC` (ABC) -- abstract base class for SQL dialect generation
- `SnowflakeDialect` (class) -- Snowflake SQL generation
- `DatabricksDialect` (class) -- Databricks SQL generation
- `MockDialect` (class) -- mock SQL generation for testing
- `MockEngine` (class) -- mock engine for testing without a warehouse
- `SnowflakeEngine` (class) -- Snowflake query execution engine
- `DatabricksEngine` (class) -- Databricks query execution engine

## Coverage Notes

- **Well-documented:** SemanticView, Metric, Dimension, Fact, OrderTerm, NullsOrdering, Row, SemolinaCursor, pool_from_config, register, unregister, MockPool
- **Covered by autoapi:** All symbols above will appear in sphinx-autoapi reference output. The gap is in prose/how-to documentation.
- **Persona-identified content gaps (from review):**
  1. No production connection pooling documentation (pool sizing, lifecycle, adbc-poolhouse)
  2. No Row-to-JSON serialization guidance for API responses
  3. No multi-pool registration end-to-end example
  4. Codegen page cross-references env vars to backend pages that only have TOML config
  5. No API endpoint integration patterns (FastAPI/Django examples)
