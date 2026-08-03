---
phase: 46-async-query-surface
reviewed: 2026-08-03T21:20:18Z
depth: standard
diff_base: 2f53869
files_reviewed: 17
files_reviewed_list:
  - src/semolina/engines/abase.py
  - src/semolina/acursor.py
  - src/semolina/config.py
  - src/semolina/registry.py
  - src/semolina/query.py
  - src/semolina/__init__.py
  - pyproject.toml
  - tests/conftest.py
  - tests/integration/conftest.py
  - tests/integration/test_async_queries.py
  - tests/unit/test_async_cancel.py
  - tests/unit/test_async_cursor.py
  - tests/unit/test_async_engine.py
  - tests/unit/test_async_packaging.py
  - tests/unit/test_async_query.py
  - tests/unit/test_asyncio_trio_matrix.py
  - tests/unit/test_registry.py
findings:
  critical: 1
  warning: 7
  info: 5
  total: 13
status: issues_found
---

# Phase 46: Code Review Report

**Reviewed:** 2026-08-03T21:20:18Z
**Depth:** standard (per-file, plus targeted execution of the async path against real DuckDB)
**Files Reviewed:** 17 (7 source/config, 10 test)
**Status:** issues_found

## Summary

The four hard architectural constraints hold. Posture A is clean — `grep` over
`src/semolina/` finds no `asyncio`/`anyio` import and no dynamic `import_module`
escape hatch, and I probed the TID251 gate directly: it catches `import asyncio`,
`import asyncio.tasks`, `import anyio.to_thread`, `from asyncio import sleep` and
`from anyio import to_thread`. `AsyncEngine`/`AsyncSemolinaCursor` are genuine
siblings with no shared base and no mode flag. The registries are two dicts and
`get_async_engine` never falls back. `import semolina` does not pull anyio.
Cursor teardown ordering (reader → cursor → connection) is correct **for the
reader the cursor creates itself**.

The defect that matters is the reader the cursor *doesn't* create. `AsyncSemolinaCursor.fetch_record_batch()`
is a public, documented passthrough that hands the caller a poolhouse reader
without recording it, so `aclose()` skips the reader-close step, both the cursor
close and the connection close then raise `ConnectionBusyError` inside
`contextlib.suppress(Exception)`, and the pooled connection is never checked in.
The docstring's own `Example:` block is a working reproducer — I ran it, and it
leaks one pool slot per execution (`checkedout()` = 1, 2, 3…). Everything else
below is a WARNING or Info.

Two other things I verified by execution rather than inference: the async
iterator diverges from its synchronous sibling after a drain (raises `OSError`
where the sync cursor yields `[]`), and the deterministic cancellation test that
claims to prove `aexecute` returns its slot on the error path never checks a
connection out at all, so `aexecute`'s `except BaseException` arm — the phase's
highest-risk twelve lines per D-08 — has no test that executes it.

Findings are ranked most severe first. Every claim marked "verified" was
reproduced against a real DuckDB async pool in this repo's venv; the two
judgement-call findings (WR-06, WR-07) are labelled as such.

## Critical Issues

### CR-01: `fetch_record_batch()` leaks its pooled connection on every call — permanently and silently

**File:** `src/semolina/acursor.py:204-234` (the passthrough), `src/semolina/acursor.py:321-350` (`aclose`), `src/semolina/acursor.py:87` (`self._reader`)

**Issue:** `AsyncSemolinaCursor.fetch_record_batch()` returns
`await self._cursor.fetch_record_batch()` without storing the reader on
`self._reader`. Only `__anext__` (line 298) ever sets `self._reader`.

adbc-poolhouse sets `AsyncConnection._reader_open = True` when a reader is
created (`_async/_cursor.py:872`) and clears it **only** in `reader.close()`
(`_async/_reader.py:323`) — draining the reader does not clear it (D-29-11).
Both `AsyncCursor.close()` and `AsyncConnection.close()` take the *foreign* tier
of that guard (`_async/_cursor.py:897`, `_async/_connection.py:701`), so with a
reader still open they raise `ConnectionBusyError`.

So the sequence is:

1. caller does `reader = await cursor.fetch_record_batch()` → `_reader_open = True`, `self._reader` stays `None`;
2. `aclose()` sees `self._reader is None` (line 344) and skips the reader-close step;
3. `await self._cursor.close()` raises `ConnectionBusyError` → swallowed by `contextlib.suppress(Exception)`;
4. `await self._conn.close()` raises `ConnectionBusyError` → swallowed;
5. `self._closed = True` was set first, so `__del__` (line 369) also stays silent.

The connection is never checked in. There is no error, no warning, and no log
line. This is not the accepted "user forgot to close the cursor" limitation —
the user *did* use `async with`.

**Verified by execution.** Running the exact `Example:` block from that method's
own docstring (`acursor.py:226-232`) in a loop against an in-memory DuckDB async
pool, fully draining the reader inside `async with`:

```
after documented example #0: checkedout=1
after documented example #1: checkedout=2
after documented example #2: checkedout=3
```

Holding the cursors alive is only needed to defeat SQLAlchemy's fairy-GC
backstop; in a real request handler the cursor stays reachable for the life of
the response, and `QueuePool` blocks once `pool_size + max_overflow` slots are
gone.

Two collateral consequences of the same root cause:

- `acursor.py:214-216` states "Close the reader before the cursor, **or let**
  `aclose()` **do it**". `aclose()` provably cannot.
- `docs/src/how-to/streaming.rst:169` repeats the promise: "``async with``
  handles that ordering for you either way."
- Calling `fetch_record_batch()` and then `async for row in cursor` makes
  `__anext__` (line 298) call `fetch_record_batch()` a second time on the same
  connection, which poolhouse rejects with `ConnectionBusyError` from inside the
  iterator.

**Fix:** record the reader so `aclose()` owns it, and make the two entry points
share one reader instead of racing for a second:

```python
async def fetch_record_batch(self) -> Any:
    if self._reader is None:
        self._reader = await self._cursor.fetch_record_batch()
    return self._reader
```

Add a test that asserts the pool invariant through the public passthrough — the
existing `test_fetch_record_batch_returns_a_reader`
(`tests/unit/test_async_cursor.py:252-263`) closes the reader by hand in a
`finally`, which is exactly what hides this:

```python
async def test_public_fetch_record_batch_still_returns_the_slot(async_duckdb_engine):
    async with await async_duckdb_engine.aexecute(_sales_query()) as cur:
        reader = await cur.fetch_record_batch()
        async for _ in reader:
            pass
    assert async_duckdb_engine._pool._pool.checkedout() == 0
```

## Warnings

### WR-01: `aclose()` converts a failed check-in into a silent permanent leak

**File:** `src/semolina/acursor.py:344-350`

**Issue:** All three teardown steps run under `contextlib.suppress(Exception)`.
The narrow-vs-`BaseException` reasoning in the docstring is right, but the
consequence is unstated: if `self._conn.close()` fails for *any* reason — the
`ConnectionBusyError` of CR-01, a driver error, a poolhouse regression — the
pool slot is gone forever and nothing anywhere records it. The class already
owns a `ResourceWarning` vocabulary in `__del__`; teardown failure deserves the
same treatment, and it is what would have surfaced CR-01 during development.

**Fix:** keep the suppression (teardown must not mask the caller's error) but
make the connection-close failure observable:

```python
try:
    await self._conn.close()
except Exception as exc:  # noqa: BLE001 - teardown must not mask the caller's error
    warnings.warn(
        f"AsyncSemolinaCursor could not return its pooled connection: {exc!r}. "
        "The pool slot is leaked.",
        ResourceWarning,
        stacklevel=2,
    )
```

### WR-02: the async iterator raises `OSError` where the sync sibling stops cleanly

**File:** `src/semolina/acursor.py:295-317` (specifically 297-298 and the comment at 301-306); compare `src/semolina/cursor.py:258-278`

**Issue:** `SemolinaCursor.__next__` wraps the `fetch_record_batch()` call in
`except (StopIteration, OSError)` → `StopIteration` (cursor.py:259-265) and does
the same for `read_next_batch()` (cursor.py:274-278), because ADBC drivers
surface drained-reader access as `OSError`. `AsyncSemolinaCursor.__anext__` has
neither arm. The in-code comment justifying the omission is about a *different*
call — it argues that poolhouse normalises the driver's end-of-stream inside
`reader.__anext__`, which is true and irrelevant to `self._cursor.fetch_record_batch()`
being invoked on an already-drained result set.

**Verified by execution** (same query, same DuckDB build, sync vs async):

```
sync:  arrow rows 2 -> iterate-after-drain -> []
async: arrow rows 2 -> iterate-after-drain RAISED OSError
       Invalid Input Error: Attempting to execute an unsuccessful or closed pending query result
```

Two written claims are false as a result: `__anext__`'s own docstring
(acursor.py:288-289, "Also raised on re-iteration of an exhausted cursor" — it
is an `OSError`, not `StopAsyncIteration`, once anything else drained the
stream), and `docs/src/how-to/streaming.rst:88` ("The contract matches the
synchronous form exactly") read against streaming.rst:69 ("treats a drained
reader as a clean `StopIteration`").

**Fix:** mirror the sync arm:

```python
if self._reader is None:
    try:
        self._reader = await self._cursor.fetch_record_batch()
    except OSError as exc:
        self._stream_exhausted = True
        raise StopAsyncIteration from exc
```

Add the test the sync path has: `fetch_arrow_table()` then `async for`, asserting
zero rows and no raise.

### WR-03: `aexecute`'s `BaseException` check-in arm is untested, and the test that claims to cover it asserts vacuously

**File:** `src/semolina/engines/abase.py:180-191`; `tests/unit/test_async_cancel.py:416-449`

**Issue:** D-08 names this handler the highest-risk part of the phase. Nothing
exercises it deterministically.

`test_cancel_before_execute_completes_propagates_and_releases_slot` cancels the
scope *before* calling `aexecute`, so the very first checkpoint — inside
`AsyncPool.connect()`'s `to_thread.run_sync` — raises, and no connection is ever
checked out. Its `assert ..._pool.checkedout() == 0` is therefore trivially true
regardless of whether the handler works, contradicting the docstring's claim
that it is "the other half: a cancellation that propagates but leaks the slot
exhausts the pool just as surely".

**Verified by tracing** `AsyncEngine.connect`:

```
trace: ['connect-start', 'raised CancelledError']
checkedout 0  checkedin 0
```

The only test that does reach the handler is
`test_deadline_over_a_semantic_view_query_is_transparent_and_recovers`, which is
gated behind `_skip_unless_measurably_slow` and a multi-second heavy fixture, and
whose `checkedout() == 0` is satisfied by poolhouse's own `on_abort=invalidate`
rather than by `conn.close()`. So on a machine where the cost ladder does not
clear the floor, nothing covers it at all.

The handler itself is correct — I confirmed a *failed* execute returns the slot
(`checkedout 0, checkedin 1` after a `semantic_view` binder error) — so this is a
coverage defect, not a behavioural one.

**Fix:** add a deterministic, fast test that forces the handler with an ordinary
execute failure:

```python
async def test_failed_execute_returns_the_slot(async_duckdb_engine):
    inner = async_duckdb_engine._pool._pool
    with pytest.raises(Exception):
        await async_duckdb_engine.aexecute(_query_against_a_missing_view())
    assert inner.checkedout() == 0
    assert inner.checkedin() == 1
```

and soften the misleading docstring on the pre-cancelled test.

### WR-04: `registry.reset()` is not exception-atomic, and its docstring says it is

**File:** `src/semolina/registry.py:214-251` (claim at 221-222, async loop at 242-251)

**Issue:** "They are always cleared even if a teardown raises, so one bad engine
cannot wedge subsequent tests" is not what the code does. Both loops suppress
only `(OSError, RuntimeError)`; anything else — the `AttributeError` the comment
at line 232 explicitly wants to propagate, or the `AttributeError` that
`async_engine._pool._pool` produces if poolhouse renames that attribute (see
WR-05) — escapes before `_engines.clear()` / `_async_engines.clear()` runs. The
next test then hits `ValueError: Async engine 'default' is already registered`
and every subsequent test in the session cascades.

`test_reset_clears_both_stores_when_async_teardown_raises`
(`tests/unit/test_registry.py`) only injects `OSError`, i.e. the one case that is
suppressed, so it cannot catch this.

**Fix:** make the clears unconditional and let the teardown error still surface:

```python
def reset() -> None:
    try:
        for engine in _engines.values():
            with contextlib.suppress(OSError, RuntimeError):
                engine.dispose()
        if _async_engines:
            from adbc_poolhouse import close_pool
            for async_engine in _async_engines.values():
                with contextlib.suppress(OSError, RuntimeError):
                    close_pool(async_engine._pool._pool)
    finally:
        _engines.clear()
        _async_engines.clear()
```

### WR-05: library code reaches into adbc-poolhouse's private `_pool` attribute, under an unbounded pin

**File:** `src/semolina/config.py:324`; `src/semolina/registry.py:250`

**Issue:** `event.listen(pool._pool, "connect", _load_semantic_views)` and
`close_pool(async_engine._pool._pool)` both depend on `AsyncPool._pool`. I
checked the installed 1.6.2 surface: `AsyncPool` exposes exactly `connect()` and
`close()` — there is no public accessor for the inner sync pool, so this is
undocumented coupling, not merely private-by-convention. The base pin is
`adbc-poolhouse>=1.6.2` with no upper bound, so a poolhouse minor release that
renames or removes that attribute breaks DuckDB async engine construction at
runtime (an `AttributeError` from inside `create_async_engine`) and wedges
`registry.reset()` per WR-04.

This is different in kind from the same access in tests, where the reviewer
comments correctly scope it as test-only.

**Fix:** at minimum, fail loudly and early with a message that names the cause:

```python
inner = getattr(pool, "_pool", None)
if inner is None:  # pragma: no cover - poolhouse contract change
    raise RuntimeError(
        "adbc-poolhouse AsyncPool no longer exposes its inner sync pool; "
        "Semolina's DuckDB semantic_views listener needs it. "
        "Pin adbc-poolhouse<next-major or file an upstream request for a public accessor."
    )
```

Better: raise the request upstream for a public accessor (or an `on_connect`
hook on `create_async_pool`) and add an upper bound to the pin until it lands.

### WR-06: the async tests hard-fail rather than skip when the `[async]` extra is absent

**File:** `pyproject.toml:49-68`, `pyproject.toml:74-89`; `justfile` `test` recipe

**Issue:** Every other optional-backend test in this suite degrades to a skip
(`pytest.importorskip("adbc_driver_duckdb")`, `pytest.importorskip("pyarrow")`).
The new async modules cannot: without anyio installed, the `pytest.mark.anyio`
marker has no plugin behind it and pytest 8.4+ *fails* the coroutine test before
any `importorskip` in the body runs. I confirmed this with `-p no:anyio`:
`21 failed, 1 passed` in `test_async_cursor.py` alone.

`uv sync --dry-run` confirms the default sync would uninstall anyio (along with
duckdb, pyarrow and 61 others), so `just test` — the gate CLAUDE.md names — goes
from "green with skips" to "red" on a default-synced environment. CI is fine
because every job passes `--extra all`.

This is a judgement call on severity: the environment was already extras-dependent
before this phase, but the *failure mode* changed from skip to error.

**Fix:** either declare the intent in the lockfile so the documented gate works —

```toml
[tool.uv]
default-extras = ["all"]
```

— or add a collection-level guard in the async modules:

```python
pytest.importorskip("anyio", reason="install semolina[async] to run the async matrix")
```

(and update the `test` recipe in the justfile to `uv run --extra all pytest`).

### WR-07: the cancellation suite is expensive and can kill the whole pytest process

**File:** `tests/unit/test_async_cancel.py:187-216` (`_hard_deadline`), `:325-366` (`heavy_database`), `:109-113` (`COST_LADDER`)

**Issue:** `heavy_database` is session-scoped, which under `pytest -n auto` (what
CI runs) means *per worker*: up to four workers each provisioning a 4–16M-row
DuckDB table and running two full uncancelled aggregates, all CPU-bound and
competing with one another, inside a job with `timeout-minutes: 10`. Locally
this module takes 14s wall / 91s CPU on a fast machine; a 2-core CI runner with
contention is a different proposition.

Worse, `faulthandler.dump_traceback_later(..., exit=True)` calls `_exit()`. When
it trips it takes down the entire interpreter — under xdist, the worker and every
unrelated result it was carrying — with no pytest report. The docstring argues
this is deliberate for the 1.6.1 deadlock, and that reasoning is sound for a
genuine hang; the concern is that the budget (`measured * 4 + 30`) is derived
from a measurement taken under whatever contention happened to exist at fixture
time, so a merely slow run can trip it.

Marked as judgement rather than confirmed: I did not observe a trip.

**Fix:** consider marking the long-query class `@pytest.mark.slow` and excluding
it from the default `-n auto` run (or pinning it to one worker with
`@pytest.mark.xdist_group`), and re-deriving the watchdog budget from a
wall-clock floor rather than only from `measured`.

## Info

### IN-01: the Posture A ban is repo-wide, not scoped to `src/semolina/` as documented

**File:** `pyproject.toml:139-150`

**Issue:** The comment and D-14 both say "the ban scopes to `src/semolina/`
only", but the config bans `asyncio`/`anyio` everywhere except `tests/**` —
including `docs/`, `semolina-jaffle-shop/` and any future script. A contributor
who imports asyncio in an unrelated example gets a Posture A lint error that does
not apply to them.

**Fix:** invert the scoping so the config matches the stated intent, e.g. keep
`TID` out of the global `select` and add
`"src/semolina/**" = ["TID251"]`-style scoping via a dedicated
`[tool.ruff.lint.per-file-ignores]` entry for everything else, or simply reword
the comment to say what it actually does.

### IN-02: dead and weak assertions in `test_async_cursor.py`

**File:** `tests/unit/test_async_cursor.py:48-52`, `:212`, `:239`, `:344`

**Issue:**
- `FIXTURE_DATA` (48-52) is defined and never referenced anywhere in the module.
- Line 344 (`assert reader.read_count == 2`) is a verbatim repeat of line 341;
  no state changes between them.
- `assert len(rows) <= 2` (212) and `all(isinstance(row, tuple) for row in rest)`
  (239) both pass on an empty result, so they do not discriminate a broken
  `fetchmany`.

**Fix:** delete `FIXTURE_DATA` and the duplicated assertion; tighten to
`assert len(rows) == 2` / `assert rest` where the fixture's row count is known.

### IN-03: `AsyncSemolinaCursor._pool` is stored and never read

**File:** `src/semolina/acursor.py:80`

**Issue:** The constructor takes and stores `pool`, but nothing in the class ever
uses it (the sync sibling at least documents an allocator-release rationale for
holding it). Dead state on a class whose lifetime discipline is the subject of
the phase invites the reader to assume the cursor can reach the pool.

**Fix:** drop the parameter, or add a one-line comment stating why the reference
is deliberately retained.

### IN-04: `create_async_engine`'s `except ImportError` can mislabel an unrelated import failure

**File:** `src/semolina/config.py:293-304`

**Issue:** The `try` wraps the whole `from adbc_poolhouse import create_async_pool`,
so *any* `ImportError` raised while poolhouse resolves its async stack (a broken
anyio install, a missing transitive dep, a partially-installed wheel) is reported
as "Async support requires the optional async dependencies. Install them with:
pip install 'semolina[async]'". The `from exc` chain preserves the truth, but the
headline sends the reader somewhere useless.

**Fix:** narrow it, e.g. `except ImportError as exc: if exc.name not in {"anyio", "adbc_poolhouse"}: raise`,
or append `(underlying: {exc})` to the message.

### IN-05: `aexecute`'s documented `ValueError` for an invalid query is an `AssertionError` in practice

**File:** `src/semolina/engines/abase.py:158`

**Issue:** `AsyncEngine.aexecute` documents `Raises: ValueError: If query is
invalid for execution`, but it never validates — validation lives in
`_Query.aexecute` (`query.py`). Calling `engine.aexecute(Sales.query())`
directly reaches the builder, which raises `AssertionError("View name not found
on field owner")`. That assertion also disappears entirely under `python -O`.

This is inherited verbatim from `Engine.execute` (`engines/base.py:156-159`), so
it is pre-existing behaviour restated in new text rather than a regression — but
the new docstring propagates the inaccuracy to the async surface.

**Fix:** either call `query._validate_for_execution()` at the top of
`AsyncEngine.aexecute` (and of `Engine.execute`), or correct both docstrings to
name the real exception.

---

_Reviewed: 2026-08-03T21:20:18Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
