# Gap Detection Report

**Source root:** `src/`
**Language:** python
**Docs root:** `docs/src/` (reStructuredText — note `paths.docs_root` in config assumes `.md`)
**Total public exported symbols:** 32 (24 from `semolina.__all__`, 8 from `semolina.engines.__all__`)
**Documented symbols (narrative docs):** 23
**Undocumented symbols (narrative docs):** 9

Every symbol below still appears in the auto-generated API reference (`sphinx-autoapi`,
`reference/api/semolina/index`). "Undocumented" here means *no narrative coverage* — the
symbol is never named in a tutorial, how-to, or explanation page, so a reader can only find
it by browsing the API tree.

## Undocumented Exports

| Symbol | File | Type | Notes |
|--------|------|------|-------|
| `Dialect` | `src/semolina/dialect.py:18` | `StrEnum` | Public re-export from `semolina`. `register()` and `create_engine()` take a dialect; no page shows the enum form. |
| `Predicate` | `src/semolina/filters.py:21` | class | Base type for filter expressions. `how-to/filtering.rst` teaches filtering but never names the type users would annotate against. |
| `SemolinaMissingDependencyError` | `src/semolina/exceptions.py:37` | exception | Raised when an optional extra is missing. No page tells the reader what to catch. |
| `DialectABC` | `src/semolina/engines/sql.py:103` | ABC | Extension point for custom dialects. |
| `SnowflakeDialect` | `src/semolina/engines/sql.py:364` | class | |
| `DatabricksDialect` | `src/semolina/engines/sql.py:441` | class | |
| `DuckDBDialect` | `src/semolina/engines/sql.py:596` | class | |
| `SnowflakeEngine` | `src/semolina/engines/snowflake.py:40` | class | Backend pages use `create_engine()` only; the concrete engine class is never shown. |
| `DatabricksEngine` | `src/semolina/engines/databricks.py:41` | class | |
| `DuckDBEngine` | `src/semolina/engines/duckdb.py:74` | class | |

## Thinly Covered (1 page only)

| Symbol | Only page |
|--------|-----------|
| `NullsOrdering` | `how-to/ordering.rst` |
| `OrderTerm` | `how-to/ordering.rst` |
| `SemolinaConnectionError` | `how-to/web-api.rst` |
| `SemolinaViewNotFoundError` | `how-to/web-api.rst` |
| `SemolinaSchemaMismatchError` | `how-to/typed-results.rst` |
| `get_engine` | `how-to/connection-pools.rst` |
| `get_async_engine` | `how-to/connection-pools.rst` |

## Notes

- **The whole `semolina.engines` namespace is narratively invisible.** All 8 exports of
  `semolina/engines/__init__.py` have zero narrative mentions. The docs consistently route
  readers through the `create_engine()` factory, which is a defensible design choice — but it
  means the `Dialect` ABC extension point has no discoverable entry, and anyone type-annotating
  an `Engine`-typed function parameter is on their own.
- **Error handling is under-documented relative to the audience.** Four public exception types
  exist; three appear on exactly one page each, one appears nowhere. For the "Python web
  developers building analytics backends" persona — who need to map warehouse failures to HTTP
  status codes — this is the sharpest gap in the set.
- **Core query surface is well covered.** `SemanticView`, `Metric`, `Dimension`, `Row`,
  `SemolinaCursor`, `create_engine`, and `register` each appear on 8–21 pages. There is no
  coverage problem in the primary path.
- **Config mismatch:** `.doc-writer/config.yaml` sets `paths.docs_root: docs/src/` but the
  tooling globs for `*.md`. This repo is Sphinx/reST — every doc file is `.rst`. A literal run
  of the gap script would report "no docs found".
