---
phase: 44-engine-owns-the-pool
reviewed: 2026-06-24T00:00:00Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - src/semolina/__init__.py
  - src/semolina/config.py
  - src/semolina/registry.py
  - src/semolina/query.py
  - src/semolina/cli/codegen.py
  - src/semolina/conftest.py
  - src/semolina/engines/base.py
  - src/semolina/engines/snowflake.py
  - src/semolina/engines/duckdb.py
  - src/semolina/engines/databricks.py
  - scripts/spike_databricks_adbc_introspect.py
  - tests/conftest.py
  - tests/integration/conftest.py
  - tests/unit/test_config.py
  - tests/unit/test_registry.py
  - tests/unit/test_pool.py
  - tests/unit/test_query.py
  - tests/unit/test_snowflake_engine.py
  - tests/unit/test_duckdb_engine.py
  - tests/unit/test_databricks_engine.py
  - tests/unit/codegen/test_cli.py
  - tests/unit/codegen/test_codegen_e2e.py
  - src/semolina/cursor.py
findings:
  critical: 1
  warning: 6
  info: 3
  total: 10
status: issues_found
---

# Phase 44: Code Review Report

**Reviewed:** 2026-06-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

Phase 44 is a clean-break refactor making `Engine` own its ADBC pool + dialect (SQLAlchemy-style), with `create_engine(config | name)` + `register(name, engine)` replacing the old `(pool, dialect)` tuple API. The dispatch logic, registry collapse, `__init__.py` surface, error translation (native → `adbc_driver_manager.*`), and the Databricks `NotImplementedError` stub are all clean and well-tested. Secret handling is sound: `SecretStr` is preserved end-to-end, the spike script never unwraps the token outside the native `connect()` boundary, and replay cassettes use placeholder credentials.

The one BLOCKER is a real connection leak in the new `Engine.execute()` path: when statement execution raises, the pooled connection is checked out but never returned. The remaining findings concern lifecycle robustness (no `__del__`/`_pool` safety net on `SemolinaCursor`, asymmetric connect handling between `execute()` and `introspect()`), substantial verbatim duplication between the retained `pool_from_config` and the new `_read_connection`, and a few stale references/heuristics left by the refactor.

## Critical Issues

### CR-01: `Engine.execute()` leaks the pooled connection when `execute()` raises

**File:** `src/semolina/engines/base.py:136-140`
**Issue:**
```python
conn = self.connect()          # checks a connection out of the pool
cur = conn.cursor()
cur.execute(sql, params)       # if this raises, conn is never returned
return SemolinaCursor(cur, conn, self._pool)
```
`self.connect()` returns `self._pool.connect()` — a checked-out connection. Unlike `introspect()` (which wraps the checkout in `with self.connect() as conn:`), `execute()` holds the raw connection with no `try/except` and no context manager. The connection is only returned to the pool by `SemolinaCursor.close()` (`self._conn.close()`), which is only reachable on the success path. If `cur = conn.cursor()` or `cur.execute(sql, params)` raises (SQL error, bad params, expired session, network failure — i.e. the *common* failure modes named in the `execute()` docstring's `Raises:`), `conn` is orphaned and never returned. With a bounded pool (`pool_size=1` is used throughout the tests/fixtures), a single failed query permanently consumes a slot; repeated failures exhaust the pool and deadlock subsequent `connect()` calls. This is a data-availability defect introduced by this phase (the pre-phase path did not own/checkout connections this way).

**Fix:** Return the connection to the pool on any failure before the cursor is handed off:
```python
conn = self.connect()
try:
    cur = conn.cursor()
    cur.execute(sql, params)
except BaseException:
    conn.close()  # return the connection to the pool, then re-raise
    raise
return SemolinaCursor(cur, conn, self._pool)
```
(Using `BaseException` also covers `KeyboardInterrupt`/`SystemExit` during a long execute.) Add a regression test that patches `connect()` to yield a cursor whose `execute()` raises, then asserts the connection was closed/returned.

## Warnings

### WR-01: `SemolinaCursor` has no finalizer and never uses its `_pool` reference — forgotten `.close()` leaks the connection

**File:** `src/semolina/cursor.py:30-52`, `288-292`
**Issue:** The cursor stores `self._pool = pool` (cursor.py:46) but it is **never read** anywhere in the class — it is dead state. Connection return to the pool happens *only* in `close()` via `self._conn.close()`. There is no `__del__` safety net, so any code path that obtains a cursor and does not explicitly `close()` it (or use it as a context manager) leaks the pooled connection until GC eventually finalizes the underlying ADBC connection — and with a `QueuePool` the slot is not reliably reclaimed by GC. Critically, the public docstrings model the leaky pattern: `src/semolina/query.py:404-413` and `src/semolina/engines/base.py:124-129` show `cursor = ....execute()` / `for row in cursor.fetchall_rows()` with **no** `.close()`. The iteration docstring (cursor.py:230) explicitly says "Iteration does NOT auto-close the cursor," confirming the leak is reachable through the documented API.
**Fix:** Either (a) add a `__del__` that best-effort returns the connection, e.g.
```python
def __del__(self) -> None:
    if not self._closed:
        with contextlib.suppress(Exception):
            self._conn.close()
```
or (b) if `_pool` was intended to drive an explicit pool-checkin distinct from `conn.close()`, wire it in — otherwise drop the unused `_pool` parameter. Update the `execute()` docstrings to show `with ... .execute() as cursor:` or a trailing `cursor.close()` so the documented happy path does not leak.

### WR-02: `execute()` and `introspect()` use incompatible `connect()` contracts

**File:** `src/semolina/engines/base.py:88-99` (definition), `:136` (execute), `src/semolina/engines/snowflake.py:163`, `src/semolina/engines/duckdb.py:157`
**Issue:** `connect()` returns `self._pool.connect()`. `introspect()` consumes it as a context manager (`with self.connect() as conn:`), which returns the connection to the pool on block exit. `execute()` consumes the *same* return value as a bare connection it keeps alive past the method (handing it to `SemolinaCursor`). The object must therefore simultaneously behave as a one-shot context manager (for introspect) and a long-lived handle (for execute). This dual contract is fragile and undocumented at the `connect()` docstring (base.py:88), which only describes the context-manager use ("a context manager that is returned to the pool on close"). The asymmetry is also why CR-01 exists only in `execute()`. The mock seams encode the split (`test_snowflake_engine.py:68` patches `connect` as a `@contextmanager`; `test_databricks_engine.py:75` patches it as `return_value=conn`), so a future change to either side will silently diverge from the other backend's tests.
**Fix:** Document both supported consumption modes in the `connect()` docstring, and (combined with CR-01) make `execute()` explicitly own connection return on failure so the lifecycle is symmetric and obvious.

### WR-03: Large verbatim duplication between `pool_from_config` and `_read_connection`

**File:** `src/semolina/config.py:68-133` vs `src/semolina/config.py:250-300`
**Issue:** `_read_connection` (the new TOML-reading half of `create_engine`'s name path) duplicates almost the entire body of the retained `pool_from_config`: opening the file, the `connections` lookup with identical `KeyError` message, the `type` pop with identical `ValueError` message, the unsupported-type check with identical message, and `_expand_private_key_path(config_cls(**section))`. Two copies of the same TOML-parsing + validation logic will drift — a bug fix or message change to one (e.g. the connection-not-found hint) silently leaves the other wrong. `warehouse_config` (config.py:303-348) contains a third partial copy of the same section-reading logic.
**Fix:** Extract the shared "read section → (config_cls, dialect, section_kwargs)" logic into one private helper and have `pool_from_config`, `_read_connection`, and `warehouse_config` all call it. Given `pool_from_config` is now superseded (see WR-04), the cleanest fix is to reimplement `pool_from_config` on top of `_read_connection` + `create_pool`.

### WR-04: `pool_from_config` is a retained, divergent legacy path that contradicts the clean-break refactor

**File:** `src/semolina/config.py:68-133`
**Issue:** The phase intent is a *clean break* from the `(pool, dialect)` tuple API to `create_engine`/`register`. Yet `pool_from_config` survives, still returns the old `(pool, Dialect)` tuple, and is documented as a public factory (`Returns: Tuple of (pool, Dialect) ready for register()`, config.py:84) — but `register()` no longer accepts a `(pool, dialect)` tuple; it takes `register(name, engine)` (registry.py:20). So the docstring describes an API that no longer exists, and the function is only exercised by `tests/unit/test_config.py` (no `src/` caller). This is dead-but-public surface that re-introduces the very tuple path the phase removed, and its `register()`-oriented docstring will actively mislead users.
**Fix:** Remove `pool_from_config` (and its tests) as part of the clean break, or — if a pool-only factory is genuinely wanted — rename/repurpose it, drop the false `register()` claim from the docstring, and fold it onto the shared helper from WR-03.

### WR-05: DuckDB introspection interpolates field names into SQL with naive quote-wrapping

**File:** `src/semolina/engines/duckdb.py:183-200`
**Issue:** Field names parsed from `DESCRIBE SEMANTIC VIEW` are interpolated into the `DESCRIBE SELECT * FROM semantic_view('...', dimensions := ['name', ...])` calls via `", ".join(f"'{n}'" for n in dims)` (and the same for metrics/facts), with no escaping of embedded single quotes. A field name containing a `'` produces malformed/injectable SQL. The values originate from the warehouse catalog (so this is lower-risk than user input), and the same pattern predates Phase 44 — per the review's "flag only if this phase WIDENED it" guidance this is **not** a BLOCKER. But Phase 44 moved this introspection onto the live ADBC `execute()` cursor path, so it is worth tracking: the introspection now runs through the same pooled-connection seam as user queries.
**Fix:** Escape single quotes (`n.replace("'", "''")`) when building the string literals, or validate field names against an identifier allowlist before interpolation. Add a test with a quote-bearing field name.

### WR-06: `registry.reset()` reaches into `engine._pool` and branches on a private poolhouse attribute

**File:** `src/semolina/registry.py:102-111`
**Issue:** `reset()` accesses `engine._pool` (a private attribute of `Engine`) and decides cleanup strategy via `hasattr(pool, "_adbc_source")` — a private implementation detail of adbc-poolhouse. If poolhouse renames/removes `_adbc_source`, every ADBC pool silently falls through to the `else: pool.close()` branch, skipping `close_pool()` and leaking ADBC driver resources, with the failure swallowed by the surrounding `contextlib.suppress(Exception)`. The blanket `suppress(Exception)` also hides genuine teardown errors. Since `reset()` is "for testing only," the impact is bounded, but the brittle private-attribute coupling is a latent maintenance hazard.
**Fix:** Prefer a public Engine method (e.g. `engine.dispose()` / `engine.close()`) that encapsulates correct pool teardown, so the registry does not reach into `_pool` or sniff poolhouse internals. Narrow the `suppress` to the specific exceptions expected during teardown.

## Info

### IN-01: Stale `pool_from_config` reference in integration conftest docstring

**File:** `tests/integration/conftest.py:21-22`
**Issue:** The module docstring still cites `:func:`semolina.config.pool_from_config`` as the credential "source of truth," but the fixtures actually use `warehouse_config` + `create_engine` (conftest.py:144-149, 202). This points readers at the superseded function (WR-04).
**Fix:** Update the reference to `warehouse_config` / `create_engine`.

### IN-02: `create_engine` and `pool_from_config` duplicate the DuckDB connect-listener wiring

**File:** `src/semolina/config.py:128-131` and `:240-243`
**Issue:** The `if dialect/conn_type is duckdb: event.listen(pool, "connect", _load_semantic_views)` block appears twice. Minor, but it is a second instance of the WR-03 copy-paste pattern and will drift the same way.
**Fix:** Centralize pool construction + DuckDB listener wiring in one helper shared by both entry points.

### IN-03: `_dialect_for_config_type` reverse lookup is correct but order-fragile by construction

**File:** `src/semolina/config.py:153-159`
**Issue:** Reverse dialect resolution iterates `_CONFIG_MAP.values()` and returns the first `isinstance(config, config_cls)` match. Verified safe today: `SnowflakeConfig`, `DatabricksConfig`, and `DuckDBConfig` are siblings under `BaseWarehouseConfig` with no subclass relationship, so no config can match two entries. This is a correctness-by-coincidence: if a future config subclasses another (e.g. a `SnowflakeGovConfig(SnowflakeConfig)`), `isinstance` would match the base entry first and silently pick the wrong dialect. No action required now; noted so a future config-class change does not introduce a silent mis-dispatch.
**Fix (defensive, optional):** Key the reverse map on `type(config)` exactly (`_CONFIG_MAP` already holds the class), falling back to `isinstance` only intentionally.

---

_Reviewed: 2026-06-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
