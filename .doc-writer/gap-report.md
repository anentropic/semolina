# Gap Detection Report

**Source root:** src/
**Language:** python
**Docs format:** reStructuredText (Sphinx + shibuya) — the `.md` pre-flight glob was adapted to `.rst`
**Total public exported symbols:** 30 (from `__all__` in `semolina`, `semolina.engines`, `semolina.testing`; `__version__` excluded)
**Documented symbols (narrative):** 14
**Undocumented symbols (narrative):** 16

> **Scope note:** Every public symbol below IS covered by the auto-generated
> `sphinx-autoapi` API reference (`reference/api/semolina/index`). "Undocumented"
> here means **absent from the narrative docs** (tutorials / how-to / explanation),
> not absent from the reference. These are narrative-coverage gaps, not missing API
> docs. Several are advanced/internal surfaces where reference-only is the right call.

## Undocumented Exports (narrative)

| Symbol | File | Type | Assessment |
|--------|------|------|------------|
| `get_pool` | `src/semolina/registry.py:73` | function | **Worth narrative** — public registry accessor; `connection-pools.rst` covers pools but never names this getter |
| `get_engine` | `src/semolina/registry.py:106` | function | **Worth narrative** — public registry accessor, peer of `register` |
| `Predicate` | `src/semolina/filters.py:21` | class | **Maybe** — base class for filter predicates; `filtering.rst` documents the lookups but not the `Predicate` base |
| `Dialect` | `src/semolina/dialect.py:18` | enum (StrEnum) | **Maybe** — public dialect selector; backends docs name dialects in prose but not this enum |
| `CredentialError` | `src/semolina/testing/credentials.py:21` | exception | **Maybe** — `warehouse-testing.rst` covers the testing pattern but not the credential error type |
| `SnowflakeCredentials` | `src/semolina/testing/credentials.py:30` | class (pydantic settings) | **Maybe** — testing-credentials surface, only indirectly referenced |
| `DatabricksCredentials` | `src/semolina/testing/credentials.py:135` | class (pydantic settings) | **Maybe** — testing-credentials surface |
| `SnowflakeEngine` | `src/semolina/engines/snowflake.py:39` | class | Low — engines are wired via `register()`; reference-only is defensible |
| `DatabricksEngine` | `src/semolina/engines/databricks.py:39` | class | Low — as above |
| `DuckDBEngine` | `src/semolina/engines/duckdb.py:66` | class | Low — as above |
| `Engine` | `src/semolina/engines/base.py:27` | ABC | Low — extension point; advanced |
| `DialectABC` | `src/semolina/engines/sql.py:40` | ABC | Low — internal extension point |
| `SnowflakeDialect` | `src/semolina/engines/sql.py:188` | class | Low — SQL-builder internal |
| `DatabricksDialect` | `src/semolina/engines/sql.py:265` | class | Low — SQL-builder internal |
| `DuckDBDialect` | `src/semolina/engines/sql.py:424` | class | Low — SQL-builder internal |
| `MockDialect` | `src/semolina/engines/sql.py:344` | class | Low — test/mock surface |

## Documented symbols (narrative)

`Dimension`, `Fact`, `Metric`, `MockEngine`, `NullsOrdering`, `OrderTerm`, `Row`,
`SemolinaCursor`, `SemolinaConnectionError`, `SemolinaViewNotFoundError`,
`SemanticView`, `pool_from_config`, `register`, `unregister` — the core
model/field/query surface a reader follows in tutorials and how-tos.

## Notes

- **Coverage is strong where it matters.** The user-facing path (`SemanticView`,
  `Metric`/`Dimension`/`Fact`, query/filter/order, `register`/`unregister`,
  `pool_from_config`, `SemolinaCursor`, the error types) is all narratively
  documented. The streaming surface (`SemolinaCursor`) was just covered by the
  Phase 39/40 how-to work.
- **Highest-value additions:** `get_pool` and `get_engine` — the only two public
  *registry* accessors with no narrative mention, sitting right beside
  `register`/`pool_from_config` which are well-covered. A short addition to
  `how-to/connection-pools.rst` would close the registry surface.
- **The `*Engine` / `*Dialect` classes are intentionally low-priority** — users
  reach engines through `register(...)`, never by importing the concrete class,
  so reference-only coverage is appropriate. Don't treat these as real gaps.
- **The `testing` credential classes** (`SnowflakeCredentials`,
  `DatabricksCredentials`, `CredentialError`) form a small coherent surface; a
  short subsection in `warehouse-testing.rst` pointing at them would help the
  data-engineer persona running live-warehouse tests.
- **Drift caught vs. the prior (May) gap report:** that report listed `get_pool`
  and `Predicate` as documented; both are currently absent from the narrative
  docs. Re-grepped and confirmed against the current tree.
