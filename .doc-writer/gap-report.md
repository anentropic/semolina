# Gap Detection Report

**Source root:** src/
**Language:** python
**Total exported symbols:** 34 (across 3 `__all__` modules)
**Documented symbols:** 25
**Undocumented symbols:** 9

## Undocumented Exports

| Symbol | File | Type |
|--------|------|------|
| `Dialect` (StrEnum) | `src/semolina/dialect.py` | enum |
| `DialectABC` | `src/semolina/engines/sql.py` | class (ABC) |
| `SnowflakeDialect` | `src/semolina/engines/sql.py` | class |
| `DatabricksDialect` | `src/semolina/engines/sql.py` | class |
| `DuckDBDialect` | `src/semolina/engines/sql.py` | class |
| `MockDialect` | `src/semolina/engines/sql.py` | class |
| `Engine` (ABC) | `src/semolina/engines/base.py` | class (ABC) |
| `CredentialError` | `src/semolina/testing/credentials.py` | exception |
| `DatabricksCredentials` | `src/semolina/testing/credentials.py` | class |

## Documented but Sparse

These symbols appear in docs but have minimal coverage:

| Symbol | Mentions | Notes |
|--------|----------|-------|
| `SnowflakeCredentials` | 0 | Only covered indirectly via codegen-credentials guide |
| `DuckDBEngine` | 0 direct | Referenced in backends/duckdb but not by class name |
| `SnowflakeEngine` | 1 | Only in backends/snowflake |
| `DatabricksEngine` | 1 | Only in backends/databricks |

## Notes

- **Core user-facing API is well-covered:** `SemanticView`, `Dimension`, `Metric`, `Fact`, `Field`, `Row`, `SemolinaCursor`, `Predicate`, `register`, `get_pool`, `pool_from_config` all have substantial documentation across tutorials and how-to guides.
- **Internal/engine-layer classes are undocumented:** The `Dialect` ABC hierarchy and `Engine` ABC are exported but not covered in user-facing docs. These are typically used internally; end users interact via `register()` and `pool_from_config()`.
- **Testing utilities undocumented:** `semolina.testing` exports (`CredentialError`, `DatabricksCredentials`, `SnowflakeCredentials`) are not covered — the warehouse-testing how-to guide covers the testing pattern but doesn't document these classes directly.
- **The `Dialect` StrEnum** (from `semolina.dialect`) is exported in the top-level `__all__` but never mentioned in docs. Users pass dialect strings to `register()` — the enum is available but not documented as a user-facing API.
- **Coverage is appropriate for the audience** — most undocumented symbols are internal/engine-level APIs covered by sphinx-autoapi reference.
