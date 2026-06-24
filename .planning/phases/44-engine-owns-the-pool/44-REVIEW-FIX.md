---
phase: 44-engine-owns-the-pool
fixed_at: 2026-06-24T00:00:00Z
review_path: .planning/phases/44-engine-owns-the-pool/44-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 44: Code Review Fix Report

**Fixed at:** 2026-06-24T00:00:00Z
**Source review:** .planning/phases/44-engine-owns-the-pool/44-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (all 5 Warnings; 0 Critical — CR-01 already resolved; Info IN-01..IN-04 out of scope)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### WR-01: `SemolinaCursor` has no finalizer; forgotten `.close()` leaks the pooled connection

**Files modified:** `src/semolina/cursor.py`, `src/semolina/query.py`, `src/semolina/engines/base.py`, `tests/unit/test_cursor.py`
**Commit:** 2ba3259
**Applied fix:** Added a best-effort `SemolinaCursor.__del__` that returns the
connection to the pool (`self._conn.close()`) when the cursor was never closed.
Guarded against partial `__init__` (uses `getattr` for `_closed`/`_conn`),
double-close (no-op when already closed), and never raises (wrapped in
`contextlib.suppress(Exception)` — finalizers must not propagate). Updated the
`execute()` docstring examples in `query.py` and `base.py` to the
`with ....execute() as cursor:` form so the documented happy path no longer
models a leak. Added three regression tests (finalizer closes a leaked conn;
finalizer does not double-close; finalizer tolerates a partially-initialised
instance).

**`_pool` decision:** Kept the `_pool` constructor parameter and the
`test_cursor.py:170` assertion. Connection checkin happens via `conn.close()`
(both in `close()` and the new `__del__`); `_pool` documents the pool-ownership
relationship and matches `execute()`'s call site. Dropping it would churn the
constructor signature and `base.py`/test call sites for no behavioural gain, so
it is retained as documented (non-behavioural) state rather than removed.

### WR-02: `execute()` and `introspect()` consume `connect()` under incompatible contracts

**Files modified:** `src/semolina/engines/base.py`
**Commit:** e25bcaa
**Applied fix:** Rewrote the `Engine.connect()` docstring to document **both**
supported consumption modes explicitly — the one-shot context-manager mode used
by `introspect()`, and the long-lived bare-handle mode used by `execute()`
(which closes the connection via `SemolinaCursor.close()` and on its own error
path, the CR-01 fix). Added the single-mode-per-checkout rule. This is the
documentation/contract clarification the review preferred over a behavioural
change; the underlying poolhouse connection already supports both modes. The
mock-seam alignment was left as-is (a noted "consider", not required) to avoid
disturbing the known-good backend tests.

### WR-03: Large verbatim duplication between `pool_from_config`, `_read_connection`, `warehouse_config`

**Files modified:** `src/semolina/config.py`, `tests/unit/test_config.py`
**Commit:** ac52921 (folded with WR-04)
**Applied fix:** Extracted a single private `_resolve_section(connection,
config_path) -> tuple[type, Dialect, dict]` helper that performs the shared TOML
open + `[connections.<name>]` lookup + `type` pop/validation, and reduced
`_read_connection` to a thin wrapper over it. The largest duplication (between
`pool_from_config` and `_read_connection`) is eliminated outright because
`pool_from_config` was deleted (WR-04). `warehouse_config` keeps its distinct
file-optional + env-merge read path (it looks sections up by backend *type*, not
section name, and tolerates a missing file) — folding it onto `_resolve_section`
would change those semantics, so only its stale `pool_from_config` docstring
reference was updated to `create_engine`.

### WR-04: `pool_from_config` is dead-but-public surface advertising the deleted `register(pool, dialect)` API

**Files modified:** `src/semolina/config.py`, `tests/unit/test_config.py`
**Commit:** ac52921 (folded with WR-03)
**Applied fix:** Confirmed via grep that `pool_from_config` had **no `src/`
caller** (only its own definition, `tests/unit/test_config.py`, and stale
docstrings). Per the clean-break v0.6 policy (no deprecation shims), **deleted**
`pool_from_config` entirely. Re-pointed the still-relevant tests onto
`create_engine` (which routes the name-dispatch path through `_read_connection`
→ `_resolve_section`): `TestConfigDispatch` (type→config-class dispatch) and
`TestConfigErrors` (missing file / missing connection / missing type /
unsupported type) now exercise `create_engine`. Deleted the `TestPoolFromConfig`
tuple-return tests and the two `pool_from_config` listener tests in
`TestSemanticViewsListener` (both already covered by `TestCreateEngine`); kept
and re-pointed the real `test_duckdb_pool_extension_loaded` end-to-end test onto
`create_engine(...)._pool`.

**Note (IN-01, out of scope):** Two stale docstring references to
`semolina.config.pool_from_config` remain in `tests/integration/conftest.py:22`
and `tests/integration/cassettes/README.md:16`. These are test/dev docstrings
not rendered by `sphinx-autoapi` (which only covers `src/semolina`), so
`just docs-build` stays clean. They were left for the IN-01 Info pass per the
`critical_warning` scope.

### WR-05: DuckDB introspection interpolates field names into `semantic_view('...')` without escaping quotes

**Files modified:** `src/semolina/engines/duckdb.py`, `tests/unit/test_duckdb_engine.py`
**Commit:** c1c1798
**Applied fix:** Added a `_sql_str_literal(value)` helper that wraps a value in
single quotes and doubles any embedded single quote (`'` → `''`), then routed
all four interpolation sites — the view name plus the dimensions, metrics, and
facts list literals — through it. Query shape is unchanged. Added unit tests for
the helper (plain value quoted; embedded quote doubled; an injection-style
`x') --` payload stays fully contained within the literal).

## Notes on logic-sensitive fixes

WR-01 (`__del__` lifecycle) and WR-06 (`reset()` exception-narrowing) are
robustness/lifecycle changes verified by syntax checks, basedpyright strict, and
targeted regression tests, plus the full `just test` suite. They are reported as
`fixed` (not `requires human verification`) because each is backed by explicit
new tests asserting the behaviour (finalizer checkin/no-double-close/partial-init
tolerance for WR-01; `close_pool` vs `pool.close()` dispatch and real-pool
teardown for WR-06).

### WR-06: `registry.reset()` reaches into private attrs under a blanket `suppress(Exception)`

**Files modified:** `src/semolina/engines/base.py`, `src/semolina/registry.py`, `tests/unit/test_registry.py`, `tests/unit/test_pool.py`
**Commit:** 23648cd
**Applied fix:** Added a public `Engine.dispose()` that encapsulates the
pool-teardown decision (`close_pool()` for ADBC-backed pools, `pool.close()`
otherwise). `registry.reset()` now calls `engine.dispose()` instead of reaching
into `engine._pool` / branching on poolhouse-private `_adbc_source` itself, and
narrows the blanket `suppress(Exception)` to `suppress(OSError, RuntimeError)`
(the errors a flaky pool close can raise during test isolation) with a
justifying comment — genuine programming errors (e.g. `AttributeError`) now
propagate instead of being hidden. Updated `_fake_engine` in the registry tests
to wire the real `Engine.dispose` (so the `close_pool` dispatch stays under
test) and added a non-ADBC stub pool default. Added `TestEngineDispose` in
`test_pool.py` (ADBC pool routes to `close_pool`; a real DuckDB engine disposes
cleanly). The many `close_pool(engine._pool)` fixture call sites were left as-is
— migrating them to `dispose()` is a broader test-suite cleanup beyond this
finding's blast radius, and the public method is now available for them.

---

_Fixed: 2026-06-24T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
