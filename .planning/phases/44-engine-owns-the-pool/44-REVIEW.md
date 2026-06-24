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
  - src/semolina/cursor.py
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
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 44: Code Review Report

**Reviewed:** 2026-06-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

This is a re-review of Phase 44 ("Engine owns the pool"). The prior review's single
BLOCKER (**CR-01**: connection leak in `Engine.execute()`'s error path) is **genuinely
resolved** and should NOT reappear: `base.py:136-149` now wraps `conn.cursor()` +
`cur.execute()` in `try/except BaseException: conn.close(); raise`, returning the
checked-out slot to the pool before propagating. The fix is backed by two real
regression tests (`test_pool.py:382-412`) that patch `connect()` to yield a
tracking connection and assert `conn.closed` for both the `cursor()`-raises and
`execute()`-raises paths. The `BaseException` choice also covers cancellation
(`KeyboardInterrupt`/`SystemExit`) during a long execute. CR-01 is closed.

Re-assessing the six prior WARNINGs against current code: five still hold unchanged
(WR-01, WR-02, WR-03, WR-04, WR-06) and one (the old WR-05 DuckDB quote-wrapping) is
re-confirmed as present but remains a non-BLOCKER pre-existing pattern. No new
BLOCKER was found. One new low-severity item surfaced: the `__version__` resolution
idiom in `__init__.py` uses an obscure `__import__("importlib.metadata")` form
(IN-04). Secret handling remains sound (`SecretStr` preserved end-to-end; the spike
unwraps the token only at the native `connect()` boundary; replay cassettes use
placeholder credentials). No async/await defects (the codebase is fully synchronous).

The remaining findings are all lifecycle-robustness and maintainability issues, not
correctness or security defects — hence no Critical tier this round.

## Narrative Findings (AI reviewer)

## Critical Issues

_None. CR-01 (connection leak in `Engine.execute()`) is fixed and regression-tested
(`src/semolina/engines/base.py:136-149`, `tests/unit/test_pool.py:361-412`)._

## Warnings

### WR-01: `SemolinaCursor` never reads its `_pool` reference and has no finalizer — a forgotten `.close()` leaks the pooled connection

**File:** `src/semolina/cursor.py:46`, `288-292` (and `tests/unit/test_cursor.py:170`)
**Issue:** `self._pool = pool` is stored (cursor.py:46) but **never read** anywhere
in the class — `grep` confirms `_pool` appears only at its assignment site. The
single "use" is a test that asserts it was stored (`test_cursor.py:170:
assert sc._pool is conn`), which locks in dead state rather than exercising
behavior. Connection return to the pool happens *only* via `close()`'s
`self._conn.close()` (cursor.py:291); there is no `__del__` safety net (`grep`
confirms no `__del__` in the class). Any code path that obtains a cursor and does
not explicitly `close()` it (or use the context manager) leaks the pooled
connection until GC finalizes the underlying ADBC connection — and a `QueuePool`
slot is not reliably reclaimed by GC. The public docstrings model exactly this
leaky pattern: `src/semolina/query.py:403-413` and `src/semolina/engines/base.py:124-129`
show `cursor = ....execute()` then `cursor.fetchall_rows()` with **no** `.close()`,
and the iteration docstring (cursor.py:230) states "Iteration does NOT auto-close
the cursor" — confirming the leak is reachable through the documented happy path.
**Fix:** Either (a) add a best-effort finalizer:
```python
def __del__(self) -> None:
    if not self._closed:
        with contextlib.suppress(Exception):
            self._conn.close()
```
or (b) wire `_pool` into an explicit pool-checkin if it was meant to drive one
distinct from `conn.close()` — otherwise drop the unused `_pool` parameter (and the
`test_cursor.py:170` assertion that pins it). Update the `execute()` docstrings in
`query.py` and `base.py` to show `with ....execute() as cursor:` or a trailing
`cursor.close()` so the documented path does not leak.

### WR-02: `execute()` and `introspect()` consume `connect()` under incompatible contracts

**File:** `src/semolina/engines/base.py:88-99` (definition), `:136` (execute),
`src/semolina/engines/snowflake.py:163`, `src/semolina/engines/duckdb.py:157`
**Issue:** `connect()` returns `self._pool.connect()`. `introspect()` consumes it as
a **context manager** (`with self.connect() as conn:`, snowflake.py:163,
duckdb.py:157), returning the connection to the pool on block exit. `execute()`
consumes the *same* return value as a **bare long-lived handle** kept alive past the
method and handed to `SemolinaCursor` (base.py:136). The object must therefore
behave simultaneously as a one-shot context manager and a long-lived connection.
The `connect()` docstring (base.py:88-99) documents only the context-manager use
("a context manager that is returned to the pool on close") and is silent on the
long-lived mode `execute()` depends on. This dual contract is now baked into the
mock seams and will silently diverge: `test_snowflake_engine.py:68` patches
`connect` as a `@contextmanager`, while `test_databricks_engine.py:75` patches it as
`return_value=conn` (a bare object). A future change to one backend's lifecycle will
not be caught by the other's tests. The asymmetry is also the structural reason
CR-01 existed only in `execute()`.
**Fix:** Document both supported consumption modes explicitly in the `connect()`
docstring, and keep `execute()`'s own error-path connection return (the CR-01 fix)
so the long-lived contract is self-contained and obvious. Consider aligning both
mock seams on one shape to prevent silent divergence.

### WR-03: Large verbatim duplication between `pool_from_config`, `_read_connection`, and `warehouse_config`

**File:** `src/semolina/config.py:68-133` vs `:250-300` (and partial third copy at `:303-348`)
**Issue:** `_read_connection` (config.py:250-300) duplicates almost the entire body
of the retained `pool_from_config` (config.py:68-133): the file open, the
`connections` lookup with an **identical** `KeyError` message
(`"Connection '{connection}' not found in {config_path}. Available connections: ..."`),
the `type`-pop with an identical `ValueError` message, the unsupported-type check
with an identical message, and `_expand_private_key_path(config_cls(**section))`.
`warehouse_config` (config.py:303-348) carries a third partial copy of the
section-reading logic. Three copies of the same TOML-parsing + validation logic will
drift: a fix or message change to one (e.g. the connection-not-found hint) silently
leaves the others stale.
**Fix:** Extract a single private helper (e.g. `_resolve_section(connection,
config_path) -> tuple[type, Dialect, dict]`) and have all three call sites use it.
Given `pool_from_config` is superseded (WR-04), reimplementing it on top of
`_read_connection` + `create_pool` is the cleanest collapse.

### WR-04: `pool_from_config` is retained dead-but-public surface whose docstring references the deleted `register(pool, dialect)` API

**File:** `src/semolina/config.py:68-133`
**Issue:** The phase intent is a *clean break* from the `(pool, dialect)` tuple API to
`create_engine`/`register(name, engine)`. Yet `pool_from_config` survives, still
returns the old `(pool, Dialect)` tuple, and its docstring still advertises
`Returns: Tuple of (pool, Dialect) ready for register()` (config.py:84) and a
`pool, dialect = pool_from_config(...)` example (config.py:96-98) — but
`register()` now takes `register(name, engine)` (registry.py:20) and no longer
accepts a tuple. `grep` confirms **no `src/` caller** of `pool_from_config`: the only
references are its own docstring, `tests/unit/test_config.py`, and stale docstrings
in `tests/integration/conftest.py` and the cassettes README. So this is dead public
surface that re-introduces the very tuple path the phase removed, with a docstring
that will actively mislead users toward a `register()` signature that no longer
exists.
**Fix:** Remove `pool_from_config` (and its dedicated tests) to complete the clean
break, or — if a pool-only factory is genuinely wanted — drop the false `register()`
claim from its docstring, rename to reflect its actual output, and fold it onto the
WR-03 shared helper.

### WR-05: DuckDB introspection interpolates catalog field names into `semantic_view('...')` literals without escaping single quotes

**File:** `src/semolina/engines/duckdb.py:183`, `:186`, `:196`
**Issue:** Field names parsed from `DESCRIBE SEMANTIC VIEW` are interpolated into the
`DESCRIBE SELECT * FROM semantic_view('...', dimensions := ['name', ...])` calls via
`", ".join(f"'{n}'" for n in dims)` (and the same for metrics/facts), with **no**
escaping of embedded single quotes (`grep` confirms no `.replace("'", "''")`). A
field name containing a `'` produces malformed or injectable SQL. The values
originate from the warehouse catalog rather than direct user input, and the pattern
predates Phase 44 — per the "flag only if this phase WIDENED it" guidance this stays
a **WARNING, not a BLOCKER**. It is carried forward because Phase 44 moved this
introspection onto the same pooled-ADBC `connect()`/cursor seam as user queries, so
it now shares that execution path.
**Fix:** Escape single quotes (`n.replace("'", "''")`) when building each string
literal, or validate field names against an identifier allowlist before
interpolation. Add a test with a quote-bearing field name.

### WR-06: `registry.reset()` reaches into `engine._pool`, branches on the private poolhouse attr `_adbc_source`, and swallows all teardown errors

**File:** `src/semolina/registry.py:102-111`
**Issue:** `reset()` accesses `engine._pool` (a private `Engine` attribute) and
selects its cleanup strategy via `hasattr(pool, "_adbc_source")` — a private
implementation detail of adbc-poolhouse. If poolhouse renames or removes
`_adbc_source`, every ADBC pool silently falls through to `else: pool.close()`,
skipping `close_pool()` and leaking ADBC driver resources — and the surrounding
blanket `contextlib.suppress(Exception)` (registry.py:104) would hide the resulting
failure along with any genuine teardown error. `Engine` exposes no public
`dispose()`/`close()` method (`grep` confirms), so `engine._pool` access is the
established pattern across the entire test suite and conftest — which is exactly why
the missing public teardown method is the real underlying gap. `reset()` is
"for testing only," bounding the blast radius, but the brittle private-attribute +
private-poolhouse-attr coupling under a blanket suppress is a latent maintenance
hazard.
**Fix:** Add a public `Engine.dispose()` (or `.close()`) that encapsulates correct
pool teardown (the `close_pool` vs `pool.close()` decision), and have `reset()` —
plus the many `close_pool(engine._pool)` call sites in fixtures — call it instead of
reaching into internals. Narrow the `suppress` to the specific exceptions expected
during teardown.

## Info

### IN-01: Stale `pool_from_config` reference in integration conftest docstring

**File:** `tests/integration/conftest.py:22` (also `tests/integration/cassettes/README.md:16`)
**Issue:** The module docstring still cites `:func:`semolina.config.pool_from_config``
as the credential "source of truth," but the fixtures actually use `warehouse_config`
+ `create_engine` (conftest.py:144-149, 202). This points readers at the superseded
function (WR-04). The cassettes README carries the same stale reference.
**Fix:** Update both references to `warehouse_config` / `create_engine`.

### IN-02: `create_engine` and `pool_from_config` duplicate the DuckDB connect-listener wiring

**File:** `src/semolina/config.py:128-131` and `:240-243`
**Issue:** The
`if duckdb: event.listen(pool, "connect", _load_semantic_views)` block appears
twice. Minor, but it is a second instance of the WR-03 copy-paste pattern and will
drift the same way (e.g. if the listener name or event changes).
**Fix:** Centralize pool construction + DuckDB listener wiring in one helper shared
by both entry points (folds naturally into the WR-03 collapse).

### IN-03: `_dialect_for_config_type` reverse lookup is correct-by-coincidence and order-fragile

**File:** `src/semolina/config.py:153-159`
**Issue:** Reverse dialect resolution iterates `_CONFIG_MAP.values()` and returns the
first `isinstance(config, config_cls)` match. Safe today: `SnowflakeConfig`,
`DatabricksConfig`, and `DuckDBConfig` are siblings with no subclass relationship, so
no config matches two entries. But if a future config subclasses another (e.g.
`SnowflakeGovConfig(SnowflakeConfig)`), `isinstance` would match the base entry first
and silently pick the wrong dialect. No action required now; noted so a future
config-class change does not introduce a silent mis-dispatch.
**Fix (defensive, optional):** Key the reverse lookup on `type(config)` exactly
(`_CONFIG_MAP` already holds the class), falling back to `isinstance` only
intentionally.

### IN-04: `__version__` uses an obscure `__import__("importlib.metadata")` idiom

**File:** `src/semolina/__init__.py:18`
**Issue:**
`__version__ = __import__("importlib.metadata").metadata.version("semolina")`.
`__import__("importlib.metadata")` returns the top-level `importlib` package (not the
submodule) but does side-effect-import `importlib.metadata` and bind it as an
attribute, so `.metadata.version(...)` resolves — verified working in an isolated
interpreter. So this is **not** a runtime bug, but it is a needlessly obscure idiom
that reads as if it might return the wrong module, and it bypasses the normal
top-of-file import. It also means an unresolvable distribution
(`PackageNotFoundError`) would fail at *import time* of the whole package.
**Fix:** Use the conventional form for clarity:
```python
from importlib.metadata import version

__version__ = version("semolina")
```
Optionally guard with `try/except PackageNotFoundError` to set a fallback (e.g.
`"0.0.0+unknown"`) for editable/uninstalled checkouts.

---

_Reviewed: 2026-06-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
