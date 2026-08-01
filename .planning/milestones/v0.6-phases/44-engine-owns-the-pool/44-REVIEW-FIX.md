---
phase: 44-engine-owns-the-pool
fixed_at: 2026-06-24T00:00:00Z
review_path: .planning/phases/44-engine-owns-the-pool/44-REVIEW.md
iteration: 2
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 44: Code Review Fix Report

**Fixed at:** 2026-06-24T00:00:00Z
**Source review:** .planning/phases/44-engine-owns-the-pool/44-REVIEW.md
**Iteration:** 2

**Summary:**
- Findings in scope: 4 (1 Critical + 3 Info; `fix_scope = all`)
- Fixed: 4
- Skipped: 0

All gates green after fixes: `prek run --all-files` Passed, `just test`
876 passed / 16 skipped (only the 7 known pre-existing
`test_queries.py::*[databricks_engine]` CassetteMissError remain — Databricks
recording hangs, explicitly out of scope), `just docs-build` build succeeded.
Net test count rose from the 871-baseline to 876 because IN-03 added 5 new
unit tests pinning the dialect mapping.

## Fixed Issues

### CR-02: `README.md` quick-start uses the deleted `pool_from_config` / 3-arg `register` API

**Files modified:** `README.md`
**Commit:** ed267ea
**Applied fix:** Rewrote the connection section to the Phase 44 API — `from
semolina import create_engine, register`, then `engine =
create_engine("default")` (reads `[connections.default]` from `.semolina.toml`)
and `register("default", engine)`, mirroring `docs/src/tutorials/first-query.rst`
and `docs/src/how-to/connection-pools.rst`. Split the query-build step from
execution (`query = Sales.query()...`) and wrapped execution in a context
manager (`with query.execute() as cursor:`) so the documented happy path
releases the pooled connection (matching the WR-01 cursor corrections).
Verified `from semolina import create_engine, register, SemanticView, Metric,
Dimension` all resolve — the README now imports only symbols exported from
`semolina/__init__.py.__all__`. `SemolinaCursor` confirmed to implement
`__enter__`/`__exit__` (`cursor.py:315-319`). blacken-docs reformatted the
`create_engine("default")` call during commit (expected).

### IN-01: Stale `pool_from_config` references in docstrings and the cassettes README

**Files modified:** `tests/integration/conftest.py`, `tests/integration/cassettes/README.md`
**Commit:** 88902c8
**Applied fix:** Replaced the dangling `:func:`semolina.config.pool_from_config``
xref (conftest.py:22) and the `semolina.config.pool_from_config` pointer
(cassettes/README.md:16) with `semolina.config.warehouse_config` — the function
the recording fixtures actually call (`conftest.py:152`, `:269`). Repo-wide grep
confirms zero `pool_from_config` / `get_pool` references remain in `tests/`,
`src/`, `docs/src/`, or `README.md`. (The only residual hit is
`docs/_build/searchindex.js`, a gitignored generated artifact that regenerates
on docs-build.)

### IN-03: `_dialect_for_config_type` reverse lookup is order-fragile

**Files modified:** `src/semolina/config.py`, `tests/unit/test_config.py`
**Commit:** 9590d03
**Applied fix:** Replaced the `isinstance`-scan over `_CONFIG_MAP.values()` with
an exact `type(config)` lookup against a `{cls: dialect}` map, raising a clear
`ValueError` listing supported configs on miss. Behaviour is identical for the
three current config classes. Added `TestDialectForConfigType` (5 tests) pinning
the mapping: exact match per backend, an unregistered subclass now raises (no
silent isinstance inheritance), and an unrelated object raises. All 5 pass.

### IN-04: `__version__` uses the obscure `__import__("importlib.metadata")` idiom

**Files modified:** `src/semolina/__init__.py`
**Commit:** fd7837e
**Applied fix:** Replaced
`__version__ = __import__("importlib.metadata").metadata.version("semolina")`
with a standard `from importlib.metadata import PackageNotFoundError, version`
plus a `try/except PackageNotFoundError` fallback to `"0.0.0+unknown"` so an
editable/source checkout without installed metadata does not raise at import.
Confirmed `import semolina; semolina.__version__` returns `0.4.0`.

## Out-of-scope references (deliberately not edited)

The IN-01 repo-wide grep surfaced `pool_from_config` / 3-arg `register` mentions
in non-shipped artifacts that are out of scope for this phase, analogous to
`.planning/`:

- `semolina-jaffle-shop/tests/conftest.py:220,291` — a **separate package**
  (own `pyproject.toml`) not yet migrated to the v0.6 Engine API; migrating it
  is its own task, not part of the Phase 44 source under review.
- `_notes/django-semolina-v0.1.md:33` — design notes for the deferred
  django-semolina helper app.
- `.doc-writer/context.md:24`, `.doc-writer/persona-report-data-engineers.md:41`
  — historical doc-writer persona/context artifacts (point-in-time notes).

These are notes/separate-package material, not user-facing shipped docs or the
reviewed source; left untouched.

---

_Fixed: 2026-06-24T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
