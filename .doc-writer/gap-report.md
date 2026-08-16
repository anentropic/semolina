# Gap Detection Report

**Source root:** src/
**Language:** python
**Doc set:** 30 `.rst` files under `docs/src/` (excluding the sphinx-autoapi-generated `docs/src/reference/api/`)

**Total exported symbols:** 34 (union of `__all__` in `semolina/__init__.py`, `semolina/exceptions.py`, `semolina/engines/__init__.py`)
**Documented symbols:** 31 (91%)
**Undocumented symbols:** 3

## Undocumented Exports

| Symbol | File | Type | Assessment |
|--------|------|------|------------|
| `DialectABC` | `src/semolina/engines/__init__.py` | abstract class | Extension point for third-party dialect authors. Covered by sphinx-autoapi reference; no narrative page targets this audience. |
| `DuckDBDialect` | `src/semolina/engines/__init__.py` | class | The DuckDB backend is documented extensively by name (`how-to/backends/duckdb.rst`, `explanation/duckdb-vs-warehouse.rst`); only the dialect *class* is unnamed, because users reach it via `create_engine`. |
| `_require` | `src/semolina/exceptions.py` | function | Underscore-prefixed and deliberately in `__all__` to declare the module's own interface. Internal by convention — not a documentation gap. |

## Notes

Coverage of the user-facing surface is effectively complete. All 25 names in the
top-level `semolina.__all__` — the surface a reader actually imports — are named in
at least one narrative page.

The three misses are all in `semolina.engines`, which is the extension layer rather
than the import surface, and one of them (`_require`) is private by naming convention.
None of the three is reachable from a task in `config.yaml`'s `user_tasks` for either
persona.

The scan therefore records no actionable gap. Symbol coverage is not the constraint on
this doc set's quality; the Editor and Persona passes below examine what is.
